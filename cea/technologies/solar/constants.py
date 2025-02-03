
"""
Parameters used for solar technologies

:References: Duffie, J. A. and Beckman, W. A. (2013) Radiation Transmission through Glazing: Absorbed Radiation, in
             Solar Engineering of Thermal Processes, Fourth Edition, John Wiley & Sons, Inc., Hoboken, NJ, USA.
             doi: 10.1002/9781118671603.ch5
"""




# pressure losses in building pipes connecting to SC/PVT
dpl_Paperm = 200
fcr = 1.3
Ro_kgperm3 = 1000
eff_pumping = 0.6
k_msc_max_WpermK = 0.217

# glazing properties for PV
n = 1.526  # refractive index of glass
K = 4  # glazing extinction coefficient

# environmental properties
Pg = 0.2  # ground reflectance

# operation temperatures
T_IN_SC_FP = 60
T_IN_SC_ET = 75
T_IN_PVT = 35

# standard testing condition (STC)
STC_RADIATION_Wperm2 = 1000