
from distutils.core import setup

setup(name='Trunnel',
      version='1.1',
      description='Trunnel binary format parser',
      author='Nick Mathewson',
      author_email='nickm@torproject.org',
      url='https://gitweb.torproject.org/trunnel.git/',
      package_dir={'': 'lib'},
      packages=['trunnel'],
      license='3-clause BSD'
      )
