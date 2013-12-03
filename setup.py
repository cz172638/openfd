#!/usr/bin/env python
# ==========================================================================
#
# Copyright (C) 2013 RidgeRun, LLC (http://www.ridgerun.com)
# All Rights Reserved.
#
# Author: Jose Pablo Carballo <jose.carballo@ridgerun.com>
#
# The contents of this software are proprietary and confidential to RidgeRun,
# LLC.  No part of this program may be photocopied, reproduced or translated
# into another programming language without prior written consent of 
# RidgeRun, LLC.
#
# Setup installation script.
#
# ==========================================================================

from distutils.core import setup

setup(name='openrfd',
      version='0.0.1',
      description='RidgeRun Firmware Installer',
      url='https://github.com/RidgeRun/u-boot-installer',
      packages=['openrfd', 'openrfd/methods', 'openrfd/methods.board',
                'openrfd/methods.sdcard'],
      scripts=['openrfd/openrfd'])