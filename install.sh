python_directory_dir="/usr/lib64/python2.7 /usr/lib64/python2.6 /usr/lib64/python2.4 /usr/lib64/python"
install_prefix="/usr/bin"

python_home_dir=''
for dir in $python_directory_dir
do
    if [ -d "$dir" ];then
        python_home_dir="$dir"
	break
    fi
done
if [ ! -d "$python_home_dir" ];then
    echo "install error: cannot find python home directory."
    exit 1
fi

python_scripts="observer_common.py observer_checker.py"
for script in $python_scripts
do
    echo cp ./"$script" "$python_home_dir"/site-packages/
    cp ./"$script" "$python_home_dir"/site-packages/
done

process_cmd="observer_start observer_stop observer_kill observer_list observer_server"
for cmd in $process_cmd
do
    echo cp -f "$cmd" $install_prefix
    cp -f "$cmd" $install_prefix 
    echo chmod 755 "$install_prefix/$cmd"
    chmod 755 "$install_prefix/$cmd"
done

echo cp -f op_observer.cfg /etc
cp -f op_observer.cfg /etc

echo cp observer /etc/rc.d/init.d/
cp observer /etc/rc.d/init.d/
echo chmod 777 /etc/rc.d/init.d/observer
chmod 777 /etc/rc.d/init.d/observer

echo chkconfig --add observer
echo
if chkconfig --add observer;then
    echo "***** install success. *****"
else
    echo "chkconfig failed."
    exit 1
fi
