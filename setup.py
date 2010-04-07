from setuptools import setup, find_packages
import os, sys


setup(
    name='csp',
    version='0.1alpha5',
    author='Michael Carter',
    author_email='CarterMichael@gmail.com',
    url='http://www.orbited.org',
    license='MIT License',
    description='An implemention of the Comet Session protocol specification for twisted: http://orbited.org/blog/files/cps.html',
    long_description='This csp implementation provides a twisted-style Port object that allows you to use existing Twisted Protocols and Factories, but listen to connections from a browser.',
    packages= find_packages(),
    zip_safe = True,
    install_requires = [],
    classifiers = [
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],        
)

