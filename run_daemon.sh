#!/bin/bash
#
# sqs_daemon      Startup script for sqs_daemon
#
# chkconfig: - 87 12
# description: sqs_daemon is a dummy Python-based daemon
# config: /etc/sqs_daemon/sqs_daemon.conf
# config: /etc/sysconfig/sqs_daemon
# pidfile: /var/run/sqs_daemon.pid
#
### BEGIN INIT INFO
# Provides: sqs_daemon
# Required-Start: $local_fs
# Required-Stop: $local_fs
# Short-Description: start and stop sqs_daemon server
# Description: sqs_daemon is a basic Python-based daemon for running an sqs listener
### END INIT INFO

# Source function library.
. /lib/lsb/init-functions  # change this line according to the distro you're running the script on

if [ -f /etc/sysconfig/sqs_daemon ]; then
        . /etc/sysconfig/sqs_daemon
fi

sqs_daemon=$2
prog=sqs_daemon
pidfile=${PIDFILE-/var/run/sqs_daemon.pid}
logfile=${LOGFILE-/var/log/sqs_daemon.log}
RETVAL=0

OPTIONS=""

start() {
        echo -n $"Starting $prog: "

        if [[ -f ${pidfile} ]] ; then
            pid=$( cat $pidfile  )
            echo $"Process id: $pid"
            isrunning=$( ps -elf | grep  $pid | grep $prog | grep -v grep )

            if [[ -n ${isrunning} ]] ; then
                echo $"$prog already running"
                return 0
            fi
        $sqs_daemon $OPTIONS
        RETVAL=$?
        #[ $RETVAL = 0 ] && success || failure
        echo
        return $RETVAL
}

stop() {
    if [[ -f ${pidfile} ]] ; then
        pid=$( cat $pidfile )
        isrunning=$( ps -elf | grep $pid | grep $prog | grep -v grep | awk '{print $4}' )

        if [[ ${isrunning} -eq ${pid} ]] ; then
            echo -n $"Stopping $prog: "
            kill $pid
        else
            echo -n $"Stopping $prog: "
            success
        fi
        RETVAL=$?
    fi
    echo
    return $RETVAL
}

reload() {
    echo -n $"Reloading $prog: "
    echo
}

# See how we were called.
case "$1" in
  start)
    start
    ;;
  stop)
    stop
    ;;
  status)
    status -p $pidfile $sqs_daemon
    RETVAL=$?
    ;;
  restart)
    stop
    start
    ;;
  force-reload|reload)
    reload
    ;;
  *)
    echo $"Usage: $prog {start|stop|restart|force-reload|reload|status}"
    RETVAL=2
esac

exit $RETVAL