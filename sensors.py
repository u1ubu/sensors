import ambient
import requests
from bluepy import btle
from inkbird_ibsth1 import GetIBSTH1Data
from vcgencmd import GetVcgencmdData
from datetime import datetime, timedelta
import os
import csv
import configparser
import pandas as pd
import requests
import logging
import subprocess

#グローバル変数
global masterdate

######Inkbird IBS-TH1のデータ取得######
def getdata_ibsth1(device):
    #値が得られないとき、最大device.Retry回スキャンを繰り返す
    for i in range(device.Retry):
        try:
            sensorValue = GetIBSTH1Data().get_ibsth1_data(device.MacAddress, device.SensorType)
        #エラー出たらログ出力
        except Exception as e:
            print(e)
            logging.warning(f'retry to get data [loop{str(i)}, date{str(masterdate)}, device{device.DeviceName}]')
            sensorValue = None
            continue
        else:
            break

    if sensorValue is not None:
        #POSTするデータ
        data = {        
            'DeviceName': device.DeviceName,        
            'Date_Master': str(masterdate),
            'Date': str(datetime.today()),
            'Temperature': str(sensorValue['Temperature']),
            'Humidity': str(sensorValue['Humidity']),
        }
        return data
    #値取得できていなかったら、ログ出力してBluetoothアダプタ再起動
    else:
        logging.error(f'cannot get data [loop{str(device.Retry)}, date{str(masterdate)}, device{device.DeviceName}]')
        #restart_hci0(device.DeviceName)
        return None

def getdata_vcgencmd(device):
    #値が得られないとき、最大device.Retry回スキャンを繰り返す
    for i in range(device.Retry):
        try:
            sensorValue = GetVcgencmdData().get(device.MacAddress, device.SensorType)
        #エラー出たらログ出力
        except Exception as e:
            print(e)
            logging.warning(f'retry to get data [loop{str(i)}, date{str(masterdate)}, device{device.DeviceName}]')
            sensorValue = None
            continue
        else:
            break

    if sensorValue is not None:
        #POSTするデータ
        data = {        
            'DeviceName': device.DeviceName,        
            'Date_Master': str(masterdate),
            'Date': str(datetime.today()),
            'Temperature': str(sensorValue['Temperature']),
        }
        return data
    #値取得できていなかったら、ログ出力してBluetoothアダプタ再起動
    else:
        logging.error(f'cannot get data [loop{str(device.Retry)}, date{str(masterdate)}, device{device.DeviceName}]')
        #restart_hci0(device.DeviceName)
        return None

######データのCSV出力######
def output_csv(data, csvpath):
    dvname = data['DeviceName']
    monthstr = masterdate.strftime('%Y%m')
    #出力先フォルダ名
    outdir = f'{csvpath}/{dvname}/{masterdate.year}'
    #出力先フォルダが存在しないとき、新規作成
    os.makedirs(outdir, exist_ok=True)
    #出力ファイルのパス
    outpath = f'{outdir}/{dvname}_{monthstr}.csv'

    #出力ファイル存在しないとき、新たに作成
    if not os.path.exists(outpath):        
        with open(outpath, 'w') as f:
            writer = csv.DictWriter(f, data.keys())
            writer.writeheader()
            writer.writerow(data)
    #出力ファイル存在するとき、1行追加
    else:
        with open(outpath, 'a') as f:
            writer = csv.DictWriter(f, data.keys())
            writer.writerow(data)

###### Ambient へ送信 ######
def SendToAmbient(data, device):
    senddata = {'created': data['Date'], 'd1': data['Temperature']}
    if 'Humidity' in data :
        senddata['d2'] = data['Humidity']
    print(f'senddata:{str(senddata)}')
    am = ambient.Ambient(device.API_URL, device.Token)
    try:
        ret = am.send(senddata)
        print('sent to Ambient (ret = %d)' % ret.status_code)
        logging.info('sent to Ambient (ret = %d)' % ret.status_code)
    except requests.exceptions.RequestException as e:
        print('Ambient.send request failed: ', e)
        logging.error(f'Ambient.send request failed:{str(e)}')

######Googleスプレッドシートにアップロードする処理######
def output_spreadsheet(all_values_dict, url):
    #APIにデータをPOST
    response = requests.post(url, json=all_values_dict)
    print(response.text)

######Bluetoothアダプタ再起動######
def restart_hci0(devicename):
    passwd = ''
    subprocess.run(('sudo','-S','hciconfig','hci0','down'), input=passwd, check=True)
    subprocess.run(('sudo','-S','hciconfig','hci0','up'), input=passwd, check=True)
    logging.error(f'restart bluetooth adapter [date{str(masterdate)}, device{devicename}]')


######メイン######
if __name__ == '__main__':    
    #開始時刻を取得
    startdate = datetime.today()
    #開始時刻を分単位で丸める
    masterdate = startdate.replace(second=0, microsecond=0)   
    if startdate.second >= 30:
        masterdate += timedelta(minutes=1)

    #設定ファイルとデバイスリスト読込
    cfg = configparser.ConfigParser()
    cfg.read(os.path.dirname(os.path.abspath(__file__)) + '/config.ini', encoding='utf-8')
    df_devicelist = pd.read_csv(os.path.dirname(os.path.abspath(__file__)) + '/DeviceList.csv')
    #全センサ数とデータ取得成功数
    sensor_num = len(df_devicelist)
    success_num = 0

    #API URL
    apiurl = cfg['API']['GoogleDriveUrl']

    #ログの初期化
    logname = f"/sensorlog_{str(masterdate.strftime('%y%m%d'))}.log"
    logging.basicConfig(filename=cfg['Path']['LogOutput'] + logname, level=logging.INFO)

    #取得した全データ保持用dict
    all_values_dict = None

    ######デバイスごとにデータ取得######
    for device in df_devicelist.itertuples():
        #Inkbird IBS-TH1
        if device.SensorType in ['Inkbird_IBSTH1mini','Inkbird_IBSTH1']:
            data = getdata_ibsth1(device)
        elif device.SensorType == 'vcgencmd' :
            data = getdata_vcgencmd(device)
        #上記以外
        else:
            data = None

        print(data)
        #データが存在するとき、全データ保持用Dictに追加し、CSV出力
        if data is not None:
            #all_values_dictがNoneのとき、新たに辞書を作成
            if all_values_dict is None:
                all_values_dict = {data['DeviceName']: data}
            #all_values_dictがNoneでないとき、既存の辞書に追加
            else:
                all_values_dict[data['DeviceName']] = data

            #CSV出力
            output_csv(data, cfg['Path']['CSVOutput'])
            #Ambient
            SendToAmbient(data, device)
            #成功数プラス
            success_num+=1

    ######Googleスプレッドシートにアップロードする処理######
    output_spreadsheet(all_values_dict, apiurl)

    #処理終了をログ出力
    logging.info(f'[masterdate{str(masterdate)} startdate{str(startdate)} enddate{str(datetime.today())} success{str(success_num)}/{str(sensor_num)}]')
