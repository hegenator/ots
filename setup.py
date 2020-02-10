from setuptools import setup

setup(
    name='Odoo TimeSheets',
    version='0.1',
    packages=['ots'],
    install_requires=[
        'BTrees',
        'Click',
        'OdooRPC',
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
