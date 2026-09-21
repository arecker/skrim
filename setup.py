import setuptools


setuptools.setup(
    name='skrim',
    version='0.0.0',
    url='https://github.com/arecker/skrim.git',
    author='Alex Recker',
    author_email='alex@reckerfamily.com',
    description='manage your skyrim mods like an adult',
    python_requires='>=3.13',
    packages=['skrim'],
    entry_points={
        'console_scripts': ['skrim=skrim.__main__:main'],
    },
    install_requires=[
        'libarchive-c==5.3',
    ],
    extras_require={
        'dev': [
            'python-lsp-server',
        ],
    },
)
