import re
import subprocess
import sys

#RaspberryPi vcgencmd データ取得クラス
class GetVcgencmdData():
    def get(self, macaddr, sensortype):
        command = 'vcgencmd measure_temp'
        result = subprocess.Popen(command, shell=True,  stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        stdout ,stderr = result.communicate()
        cpuTemp = re.search(r'[\d]+[.]*[\d]*', stdout.split()[0])
        sensorValue = {
                'SensorType': 'vcgencmd',
                'Temperature': cpuTemp.group(),
                'Humidity': 0,
                'unknown1': 0,
                'unknown2': 0,
                'unknown3': 0,
            }
        return sensorValue

