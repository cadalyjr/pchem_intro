"""
This code was written by Clyde Daly during 06/21.

This code sets up a set of simulations for umbrella sampling.
The two bodies are first pulled to a reasonable starting location,
then are pulled along the coordinate of interest.
A user must edit this code to correctly identify which bodies in
the simulaion are being pulled along the coordinate.
It is also important to consider the symmetry of your system -
does a spherically symmetric coordinate make sense for a
rectangular system?

The structure given to this code as should already be equilibrated.

Data is printed in umbrella_setup.dat about the simlation state and
umbrella_setup.h5 writes the simulation frames.
"""

from simtk.openmm.app import *
from simtk.openmm import *
from simtk.unit import *
from sys import stdout
import mdtraj as md
import numpy as np

import argparse

#import pdb file, import FF
pdb = PDBFile('equilibrated_structure.pdb')
forcefield = ForceField('charmm36.xml', 'charmm36/water.xml')
print('loaded FF and pdb')

#create the simulation system
system = forcefield.createSystem(pdb.topology, nonbondedMethod=PME,
        nonbondedCutoff=1.0*nanometer, constraints=HBonds)
print('system built')

#create atom groups <- users will likely need to edit this
ACP = [k for k in pdb.topology.chains()][2]
g1 = [k.index for k in (ACP.atoms())] #the first group of atoms
KS = [k for k in pdb.topology.chains()][:2]
g2 = [] #the second group of atoms
for k in KS:
    for j in k.atoms():
        g2.append(j.index)
print('atoms grouped')

#add a force pulling the bodies apart <- users will likely need to edit this section
force = CustomCentroidBondForce(2, "k*(distance(g1,g2)-r0)^2")
force.addGlobalParameter("k", 100.0*kilocalories_per_mole/angstroms**2) #this force worked for two large proteins
force.addGlobalParameter("r0", 39.0*angstroms) #this will change during the simulation
force.addGroup(g1) #adding atom group 1 from earlier
force.addGroup(g2) #adding atom group 2 from earlier
force.addBond([0, 1], []) #adding a bond between the groups is really important
system.addForce(force)
print('pulling force added')

#finish setting up the simulation
integrator = LangevinMiddleIntegrator(300.0*kelvin, 1.0/picosecond, 0.002*picoseconds)
simulation = Simulation(pdb.topology, system, integrator)
simulation.context.setPositions(pdb.positions)
print('simulation ready')

#if needed minimize the energy with the constraint, reset temp.
#this can be useful because the added force can be a large perturbation.
#simulation.minimizeEnergy()
#simulation.context.setVelocitiesToTemperature(300.0*kelvin)
#print('minimized, velocities set to 300 K')

#report output
simulation.reporters.append(StateDataReporter('umbrella_setup.dat', 10000,
                                                step=True,
                                                totalEnergy=True,
                                                potentialEnergy=True,
                                                temperature=True,
                                                kineticEnergy=True,
                                                volume=True,
                                                progress=True,
                                                speed=True,
                                                totalSteps=15*500000)) #15 ns
simulation.reporters.append(md.reporters.HDF5Reporter('umbrella_setup.h5', 10000))
print('reporters appended')

#pull proteins apart - right now, the code assumes it takes 5 ns to
#1. Equilibrate the bodies in the presence of the added force and
#2. Pull the bodies to a good starting location
print('equilibration with the force')
#setup_steps = int(5*1000*1000/2) #5 ns
simulation.step(500000)

print('pulling protein to setup')
for i in np.arange(4):
    r0 = 39.0-i*3.0
    simulation.context.setParameter('r0', r0*angstroms) #this updates the optimal distance
    simulation.step(500000)
    print('distance constant is', r0, 'Angstroms')

#for my original use, I sampled 10 distances and gave each a nanosecond to equilibrate.
#this may change for other users.
print('pulling protein to sample')
ts = 10
sample_steps = int(ts*1000*1000/2) #10 ns
for i in np.arange(ts):
    r0 = 30.0+i*3.0
    simulation.context.setParameter('r0', r0*angstroms) #this updates the optimal distance
    simulation.step(sample_steps//ts)
    print('distance constant is', r0, 'Angstroms')
    state = simulation.context.getState(getEnergy=True,
                            getForces=True,
                            getPositions=True,
                            enforcePeriodicBox=True)
    positions = state.getPositions()
    simulation.topology.setPeriodicBoxVectors(state.getPeriodicBoxVectors())
    PDBFile.writeFile(simulation.topology, positions,
    open('umbrella_starter_{}.pdb'.format(i+1), 'w'))
    simulation.saveState('umbrella_starter_{}.xml'.format(i+1)) #usefully, this file will contain information about r0 for this simulation
