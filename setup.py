from setuptools import setup

setup(
  name="bakonf",
  version="0.7.0",
  scripts=["bakonf.py"],
  python_requires=">=3.6",
  install_requires="bsddb3",

  author="Iustin Pop",
  author_email="iustin@k1024.org",
  description="Simple backup tool",
  keywords="backup",
  url="http://github.com/iustin/bakonf",
  project_urls={
    "Bug Tracker": "https://github.com/iustin/bakonf/issues",
    },
  classifiers=[
    "Environment :: Console",
    "Development Status :: 5 - Production/Stable",
    "Intended Audience :: System Administrators",
    "License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)",
    "Operating System :: Unix",
    "Operating System :: POSIX :: Linux",
    "Topic :: System :: Archiving :: Backup",
    "Topic :: Utilities",
  ],
)
