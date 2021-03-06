#!/usr/bin/env python
# ==========================================================================
#
# Copyright (C) 2013 RidgeRun, LLC (http://www.ridgerun.com)
#
# Author: Jose Pablo Carballo <jose.carballo@ridgerun.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# U-Boot environment operations to support the installer.
#
# ==========================================================================

# ==========================================================================
# Imports
# ==========================================================================

import openfd.utils as utils

# ==========================================================================
# Public Classes
# ==========================================================================

class EnvInstaller(object):
    """Handles operations with U-Boot's environment."""
    
    def __init__(self, uboot, dryrun=False):
        """
        :param uboot: :class:`Uboot` instance.
        :param dryrun: Enable dryrun mode. System and uboot commands will be
            logged, but not executed.
        :type dryrun: boolean
        """
        
        self._l = utils.logger.get_global_logger()
        self._e = utils.executer.get_global_executer()
        self._u = uboot
        self._dryrun = dryrun
        self._e.dryrun = dryrun
        self._u.dryrun = dryrun
        
    def __set_dryrun(self, dryrun):
        self._dryrun = dryrun
        self._e.dryrun = dryrun
        self._u.dryrun = dryrun
    
    def __get_dryrun(self):
        return self._dryrun
    
    dryrun = property(__get_dryrun, __set_dryrun,
                     doc="""Enable dryrun mode. System and uboot commands will
                     be logged, but not executed.""")
    
    def install_variable(self, variable, value, force=False):
        """
        Installs a variable in uboot's environment. If the same variable has
        already been installed it will avoid re-installing it, unless `force`
        is specified.

        :param variable: Uboot's environment variable to install (i.e. bootargs,
            bootcmd, mtdparts, etc.).
        :param value: Value to set in the environment variable.
        :param force: Forces the installation.
        :type force: boolean
        """
        
        self._l.info("Installing %s" % variable)
        value = value.strip()
        if not force:
            self._l.debug("Verifying if %s installation is needed" % variable)
            value_on_board = self._u.get_env(variable)
            if value == value_on_board:
                self._l.info("%s doesn't need to be installed" %
                             variable.capitalize())
                return
        self._u.set_env(variable, value)
        self._u.save_env()
        self._l.info("%s installation complete" % variable.capitalize())
    
