Summary: A configuration file backup tool
Name: bakonf
Version: 0.2
Release: 1
License: GPL
Vendor: Iustin Pop
Packager: Iustin Pop <oss@k1024.org>
Group: Applications/System
URL: http://www
Source0: %{name}-%{version}.tar.gz
BuildRoot: %{_tmppath}/%{name}-%{version}-buildroot
BuildArch: noarch

%description
bakonf is a tool designed to make backups of the configuration
files of a GNU/Linux or Unix-like system. Its aim is to use
various methods in order to reduce the size of the backup to a
reasonable minimum, in order to be useful for remote/unattended
servers.
%prep
%setup -q

%build

%install
rm -rf $RPM_BUILD_ROOT
make install DESTDIR=$RPM_BUILD_ROOT

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
/usr/libexec/bakonf
/etc/bakonf
/usr/sbin/bakonf
%doc /usr/share/doc/%{name}-%{version}

%changelog
* Wed Dec 11 2002 Iustin Pop <iusty@yahoo.com> 
- Initial build.
