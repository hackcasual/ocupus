import shlex
import subprocess
import zmq
import time
from multiprocessing import Process, Value, Queue

class ManagedProcess:
    processes = []

    def __init__(self, commandLine, category, name, shouldRestart):
        self.commandLine = commandLine
        self.category = category
        self.name = name
        self.shouldRestart = shouldRestart
        self.shutdownFlag = Value('B', 0)
        ManagedProcess.processes.append(self)

    @staticmethod
    def system_shutdown():
        for p in ManagedProcess.processes:
            p.shutdownFlag.value = 1

        leftAlive = False
        for p in ManagedProcess.processes:
            try:
                if p.managedProcess.is_alive():
                    leftAlive = True
            except:
                pass

        if not leftAlive:
            return

        time.sleep(1.0)

        for p in ManagedProcess.processes:
            try:
                p.managedProcess.terminate()
            except:
                pass


    def start(self):
        self.managedProcess = Process(target=self._run, args=(self.shutdownFlag,))
        self.managedProcess.start()

    def stop(self):
        self.shutdownFlag.value = 1
        self.managedProcess.join()

    def _run(self, shutdown):
        context = zmq.Context()
        processControl = context.socket(zmq.SUB)
        processControl.connect ("tcp://localhost:5554")
        processControl.setsockopt(zmq.SUBSCRIBE, "process_control:%s:%s" % (self.category, self.name))

        context = zmq.Context()

        logger = context.socket(zmq.REQ)
        logger.connect ("tcp://localhost:5550")

        args = shlex.split(self.commandLine)

        proc = subprocess.Popen(args)

        while not shutdown.value:
            events = processControl.poll(timeout=100)

            if events != 0:
                pass

            retcode = proc.poll()

            if retcode is None:
                continue

            logger.send_json({"type":"process_status", "data":{
                "event": "exit",
                "retcode": retcode,
                "name": self.name,
                "category": self.category,
                "commandLine": self.commandLine
                }})
            logger.recv()

            if self.shouldRestart:
                time.sleep(0.1)
                print("Restarting process %s:%s" % (self.category, self.name))
                proc = subprocess.Popen(args)
                logger.send_json({"type":"process_status", "data":{
                    "event": "restarting",
                    "name": self.name,
                    "category": self.category,
                    "commandLine": self.commandLine
                    }})
                logger.recv()
            else:
                shutdown.value = 1

        self._stop_child(proc)


    def _stop_child(self, proc):
        if proc.poll() is None:
            proc.terminate()
            for i in range(10):
                if proc.poll() is not None:
                    return True
                time.sleep(0.100)
            print("Needed to kill the process")
            proc.kill()
            return False
        return True
