from flask import Flask, render_template, request
import json
from datetime import datetime, timedelta
import psycopg2
import numpy as np
from skyfield.api import load, EarthSatellite
import matplotlib

matplotlib.use('Agg')
app = Flask(__name__)


# Функция для подключения к базе данных
def get_db_connection():
    conn = psycopg2.connect(dbname='satellites', user='postgres',
    password = '3141592', host = 'localhost')
    return conn


# Первая страница
@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM tle;')  # Запрос всех имен спутников из базы данных
    names = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return render_template('index.html', names=names)  # Отправляем массив имен спутников в index.html для выбора спутника


# Функция для получения траектории спутника за последние три часа
@app.route('/past_trajectory', methods=['POST'])
def past_trajectory():
    name = request.json['name']  # Получаем имя спутника из запроса
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT firststring, secondstring FROM tle WHERE name=%s;', (name,))
    firstStringTLE, secondStringTLE = cursor.fetchone()
    cursor.close()
    conn.close()

    ts = load.timescale()  # Загружаем шкалу времени
    now = datetime.utcnow()  # Текущее время в UTC
    t_now = ts.utc(now.year, now.month, now.day, now.hour, now.minute,
               now.second)  # Преобразуем текущее время в формат Skyfield

    # Создаем объект спутника с помощью TLE данных
    satellite = EarthSatellite(firstStringTLE, secondStringTLE, name, ts)

    latitudes = []
    longitudes = []

    # Траектория спутника за последние три часа (10800 секунд)
    for i in range(10800):
        past_time = t_now - timedelta(seconds=i)  # Отнимаем секунды от теку-щего времени
        geocentric = satellite.at(past_time)  # Получаем геоцентрическое по-ложение спутника
        subpoint = geocentric.subpoint()  # Получаем подспутниковую точку (широта и долгота)

        latitudes.append(subpoint.latitude.degrees)  # Добавляем широту в список
        longitudes.append(subpoint.longitude.degrees)  # Добавляем долготу в список

# Возвращаем траекторию в формате JSON
    return json.dumps({
    'trajectory': {'latitudes': latitudes, 'longitudes': longitudes}
})


# Маршрут для получения текущей позиции спутника и его траектории
@app.route('/current_position', methods=['POST'])
def current_position():
    name = request.json['name']  # Получаем имя спутника из запроса
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT firststring, secondstring FROM tle WHERE name=%s;',
                   (name,))  # запрос в бд строк TLE по имени спутника
    firstStringTLE, secondStringTLE = cursor.fetchone()
    cursor.close()
    conn.close()

    ts = load.timescale()  # Загружаем шкалу времени
    now = datetime.utcnow()  # Текущее время в UTC
    t = ts.utc(now.year, now.month, now.day, now.hour, now.minute,
               now.second)  # Преобразуем текущее время в формат Skyfield
    satellite = EarthSatellite(firstStringTLE, secondStringTLE, name,
                               ts)  # Создаем объект спутника с помощью TLE данных
    geocentric = satellite.at(t)  # Получаем геоцентрическое положение спут-ника
    subpoint = geocentric.subpoint()  # Получаем подспутниковую точку (широта и долгота)

    latitude = subpoint.latitude.degrees  # Широта текущего положения спутника
    longitude = subpoint.longitude.degrees  # Долгота текущего положения спутника

    # Вычисление траектории спутника
    orbit_period_minutes = 2 * np.pi / satellite.model.no_kozai  # Орбитальный период спутника в минутах
    times = ts.utc(now.year, now.month, now.day, now.hour,
                   range(now.minute - int(orbit_period_minutes), now.minute))  # Моменты времени для траектории

    geocentric_trajectory = satellite.at(times)  # Получаем геоцентрические положения спутника в указанные моменты времени
    subpoints = geocentric_trajectory.subpoint()  # Получаем подспутниковые точки
    latitudes = subpoints.latitude.degrees.tolist()  # Широты траектории
    longitudes = subpoints.longitude.degrees.tolist()  # Долготы траектории

    # Интерполяция траектории для сглаживания
    smooth_latitudes = np.interp(np.linspace(0, len(latitudes) - 1, num=100), np.arange(len(latitudes)), latitudes)
    smooth_longitudes = np.interp(np.linspace(0, len(longitudes) - 1, num=100), np.arange(len(longitudes)), longitudes)

    # Возвращаем текущую позицию и траекторию в формате JSON
    return json.dumps({
        'latitude': latitude,
        'longitude': longitude,
        'trajectory': {'latitudes': smooth_latitudes.tolist(), 'longitudes': smooth_longitudes.tolist()}
    })


@app.route('/satellite', methods=['POST'])
def satellite():
    name = request.form['name']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT firststring, secondstring FROM tle WHERE name=%s;',(name,))  # запрос в бд по имени выбранного спутника
    firstStringTLE, secondStringTLE = cursor.fetchone()
    cursor.execute('SELECT name FROM tle;')  # запрос в бд всех имен спутников
    names = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    data = [name, firstStringTLE, secondStringTLE]

    #  Парсинг данных  #
    #     Строка 1     #

    stringNumber1 = data[1][0:1]  # Номер строки
    satelliteNumber1 = data[1][2:7]  # Номер спутника в базе данных NORAD
    classification = data[1][7:8]  # Классификация (U=Unclassified — не секретный)
    internDesignation_Year = data[1][9:11]  # Международное обозначение (последние две цифры года запуска)
    internDesignation_Number = data[1][11:14]  # Международное обозначение (номер запуска в этом году)
    internDesignation_Part = data[1][14:17]  # Международное обозначение (часть запуска)
    yearOfEpoch = data[1][18:20]  # Год эпохи (последние две цифры)
    timeOfEpoch = data[1][20:32]  # Время эпохи (целая часть — номер дня в году, дробная — часть дня)
    firstDerivative = data[1][33:43]  # Первая производная от сред-него движения (ускорение), делённая на два [виток/день^2]
    secondDerivative = data[1][44:52]  # Вторая производная от сред-него движения, делённая на шесть (подразумевается, что число начинается с де-сятичного разделителя) [виток/день^3]
    dragCoefficient = data[1][53:61]  # Коэффициент торможения B* (подразумевается, что число начинается с десятичного разделителя)
    typesOfEphemeris = data[1][62:63]  # Изначально — типы эфемерид, сейчас — всегда число 0
    itemNumber = data[1][64:68]  # Номер (версия) элемента
    checksum1 = data[1][68:69]  # Контрольная сумма по модулю 10

    #     Строка 2     #

    stringNumber2 = data[2][0:1]  # Номер строки
    satelliteNumber2 = data[2][2:7]  # Номер спутника в базе данных NORAD
    slant = data[2][8:16]  # Наклон в градусах
    longitudeOfAscendingNode = data[2][17:25]  # Долгота восходящего узла в градусах
    eccentricity = data[2][26:33]  # Эксцентриситет (подразуме-вается, что число начинается с десятичного разделителя)
    pericenterArgument = data[2][34:42]  # Аргумент перицентра в гра-дусах
    averageAnomaly = data[2][43:51]  # Средняя аномалия в градусах
    frequencyOfTreatment = data[2][52:63]  # Частота обращения (оборотов в день) (среднее движение) [виток/день]
    turnNumber = data[2][63:68]  # Номер витка на момент эпохи
    checksum2 = data[2][68:69]  # Контрольная сумма по модулю 10

    return render_template('satellite.html', names=names, data=data, stringNumber1=stringNumber1,satelliteNumber1=satelliteNumber1,classification=classification, internDesignation_Year = internDesignation_Year, internDesignation_Number = internDesignation_Number, internDesignation_Part = internDesignation_Part, yearOfEpoch = yearOfEpoch, timeOfEpoch = timeOfEpoch, firstDerivative = firstDerivative, secondDerivative = secondDerivative, dragCoefficient = dragCoefficient, typesOfEphemeris = typesOfEphemeris, itemNumber = itemNumber, checksum1 = checksum1, stringNumber2 = stringNumber2, satelliteNumber2 = satelliteNumber2, slant = slant, longitudeOfAscendingNode = longitudeOfAscendingNode, eccentricity = eccentricity, pericenterArgument = pericenterArgument, averageAnomaly = averageAnomaly, frequencyOfTreatment = frequencyOfTreatment, turnNumber = turnNumber, checksum2 = checksum2)
    # в satellite.html отправили распаршенные данные TLE
if __name__ == '__main__':
    app.run(debug=True)
