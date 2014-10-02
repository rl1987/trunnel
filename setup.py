
from distutils.core import setup

namespace = {}
exec(open("./lib/trunnel/__init__.py").read(), namespace)

setup(name='Trunnel',
      version=namespace['__version__'],
      description='Trunnel binary format parser',
      author='Nick Mathewson',
      author_email='nickm@torproject.org',
      url='https://gitweb.torproject.org/trunnel.git/',
      packages=['trunnel'],
      package_dir={'': 'lib'},
      package_data={'trunnel': ['data/*.c', 'data/*.h']},
      license='3-clause BSD'
      )
