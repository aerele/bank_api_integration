# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

with open('requirements.txt') as f:
	install_requires = f.read().strip().split('\n')

# get version from __version__ variable in bank_api_integration/__init__.py
from bank_api_integration import __version__ as version

setup(
	name='bank_api_integration',
	version=version,
	description='Implementation of bank api integration',
	author='Aerele',
	author_email='admin@aerele.in',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires,
	dependency_links=[
		'git+https://github.com/aerele/bankingapi.git#egg=banking_api-0.1.0'],
	python_requires='>=3.6'
)
