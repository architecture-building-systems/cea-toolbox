"""    Cost Mapping    """  

"""
this script aims to map the cost of each plant

WORK IN PROCESS 

"""


# Mapping CC Cost


#Energy_Models_path ="/Users/Tim/Desktop/ETH/Masterarbeit/Github_Files/urben/Masterarbeit/EnergySystem_Models"
#M_to_S_Var_path = "/Users/Tim/Desktop/ETH/Masterarbeit/Github_Files/urben/Masterarbeit/M_and_S/Slave/Trials"

#import os
import numpy as np
#os.chdir(Energy_Models_path)
import EnergySystem_Models.Model_CC as MCC
import globalVar as gV

#os.chdir(M_to_S_Var_path)
#import Master_to_Slave_Variables as MS_Var
#reload(MS_Var)
#os.chdir(Energy_Models_path)


#import MasterToSlaveVariables
#reload(MasterToSlaveVariables)
#context = MasterToSlaveVariables.MasterSlaveVariables()
#MS_Var = context

#reload (gV)
reload (MCC)

#TO BE ITERATED!
#fuel = 'NG'
#tDH = 60 + 273.0



# TRY 2 - iterating and mapping the thermal output

it_len = 50

Qel_min = gV.GT_minSize
Qel_max = gV.GT_maxSize 
phi_min = gV.GT_minload


import matplotlib.pyplot as plt

  
        
tDH = 70.0 + 273
fuel = 'NG'


Q_design_range = np.linspace(Qel_min, Qel_max, it_len)
wdotfin = np.zeros( (it_len, it_len) )
qdot = np.zeros( (it_len, it_len) )
eta_elec = np.zeros( (it_len, it_len) )
eta_heat = np.zeros( (it_len, it_len) )
eta_all = np.zeros( (it_len, it_len) )


i = 0
for Q_it in range(len(Q_design_range)):
    Q_design = Q_design_range[Q_it]
    wdot_range = np.linspace(Q_design*phi_min, Q_design, it_len)
    
    for wdot_it in range(len(wdot_range)):
        wdot_in = wdot_range[wdot_it]
        
        if wdot_in <= phi_min * Q_design:
            wdot_in = phi_min * Q_design + 0.001 
            print "changed"
            
        CC_OpInfo = MCC.CC_Op(wdot_in, Q_design, fuel, tDH)
        
        if wdot_in <= phi_min * Q_design:
            CC_OpInfo = [0,0,0,0,0]
        wdotfin[Q_it, wdot_it] = CC_OpInfo[0]
        qdot[Q_it, wdot_it] = CC_OpInfo[1]
        eta_elec[Q_it, wdot_it] = CC_OpInfo[2]
        eta_heat[Q_it, wdot_it] = CC_OpInfo[3]
        eta_all[Q_it, wdot_it] = CC_OpInfo[4]
        i += 1
        print i

        #print x,k
            

from scipy import interpolate
from mpl_toolkits.mplot3d import Axes3D

wdot_partload = wdot_range / np.amax(Q_design_range)

f1 = interpolate.interp2d(Q_design_range, wdot_range, wdotfin, kind = 'cubic')
f2 = interpolate.interp2d(Q_design_range, wdot_range, qdot, kind = 'cubic')
f3 = interpolate.interp2d(Q_design_range, wdot_range, eta_elec, kind = 'cubic')
f4 = interpolate.interp2d(Q_design_range, wdot_range, eta_heat, kind = 'cubic')
f5 = interpolate.interp2d(Q_design_range, wdot_range, eta_all, kind = 'cubic')




#C_furn_interp = f1(Q_therm, y1,




"""# PLOTTING """

fig = plt.figure()
ax = Axes3D(fig)

X1,Y1 = np.meshgrid(Q_design_range / 10E6 ,wdot_partload)
Z = f2(Q_design_range, wdot_range)
ax.plot_surface(X1, Y1, Z)

ax.set_xlabel("GT Electric Design Size [MW]")
ax.set_ylabel("Electric Partload of GT [-]")
ax.set_zlabel("Total Thermal Energy Output CC [MWh]")
ax.plot_surface(X1, Y1, Z, rstride=1, cstride=1, cmap='RdYlBu_r', linewidth = 0, antialiased = False)

#fig.colorbar(ax, shrink=0.5, aspect=5)

plt.show()



