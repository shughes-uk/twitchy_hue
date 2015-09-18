from distutils.core import setup
import py2exe

setup(
    console=['twitchy_hue.py'],
    zipfile=None,
    options={
            'py2exe':{
                    'bundle_files' : 1,
                    'compressed' : True
                    }
            }
    )
