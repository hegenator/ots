from setuptools import setup
from ots.__about__ import __version__

setup(
    name='Odoo TimeSheets',
    version=__version__,
    packages=[
        'ots',
        'ots.migration',
    ],
    install_requires=[
        'BTrees',
        'Click',
        'OdooRPC',
        'packaging',
        'persistent',
        'python-dateutil',
        'tabulate',
        'ZODB',
    ],
    python_requires='>=3.6',
    entry_points='''
        [console_scripts]
        ots=ots.cli:cli
    ''',
)
