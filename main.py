from flask import Flask, request

from geo import get_country
import logging
import json
import random
import os


app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

cities = {
    'москва': ['997614/bd47789a3241e42d7b79', '997614/fb3c188205283c09b0ea'],
    'нью-йорк': ['997614/3b421cfc3ba6113a54cc', '1540737/2434185d7eae3415b092'],
    'париж': ["213044/9752748f1f91e0f91606", '997614/413d7449a1a1d6eee90c']
}

sessionStorage = {}


@app.route('/post', methods=['POST'])
def main():
    logging.info('Request: %r', request.json)
    response = {
        'session': request.json['session'],
        'version': request.json['version'],
        'response': {
            'end_session': False
        }
    }
    handle_dialog(response, request.json)
    logging.info('Response: %r', response)
    return json.dumps(response)


def handle_dialog(res, req):
    user_id = req['session']['user_id']
    res['response']['buttons'] = [{'title': 'Помощь', 'hide': False}]
    if req['session']['new']:
        res['response']['text'] = 'Привет! Назови своё имя!'
        sessionStorage[user_id] = {
            'first_name': None,  # здесь будет храниться имя
            'game_started': False  # здесь информация о том, что пользователь начал игру. По умолчанию False
        }
        return

    if 'помощь' in req['request']['nlu']['tokens']:
        res['response']['text'] = 'Игра "Угадай Город". Алиса показывает пользователю фотографию города,' \
                                  ' а он должен его отгадать.'
        return

    if sessionStorage[user_id]['first_name'] is None:
        first_name = get_first_name(req)
        if first_name is None:
            res['response']['text'] = 'Не расслышала имя. Повтори, пожалуйста!'
        else:
            sessionStorage[user_id]['first_name'] = first_name
            # создаём пустой массив, в который будем записывать города, которые пользователь уже отгадал
            sessionStorage[user_id]['guessed_cities'] = []
            # как видно из предыдущего навыка, сюда мы попали, потому что пользователь написал своем имя.
            # Предлагаем ему сыграть и два варианта ответа "Да" и "Нет".
            res['response']['text'] = f'Приятно познакомиться, {first_name.title()}. Я Алиса. Отгадаешь город по фото?'
            res['response']['buttons'] = [
                {
                    'title': 'Да',
                    'hide': True
                },
                {
                    'title': 'Нет',
                    'hide': True
                }
            ]
    else:
        first_name = sessionStorage[user_id]['first_name'].title()
        # У нас уже есть имя, и теперь мы ожидаем ответ на предложение сыграть.
        # В sessionStorage[user_id]['game_started'] хранится True или False в зависимости от того,
        # начал пользователь игру или нет.
        if not sessionStorage[user_id]['game_started']:
            # игра не начата, значит мы ожидаем ответ на предложение сыграть.
            if 'да' in req['request']['nlu']['tokens']:
                # если пользователь согласен, то проверяем не отгадал ли он уже все города.
                # По схеме можно увидеть, что здесь окажутся и пользователи, которые уже отгадывали города
                if len(sessionStorage[user_id]['guessed_cities']) == 3:
                    # если все три города отгаданы, то заканчиваем игру
                    res['response']['text'] = first_name + ', ты отгадал все города!'
                    res['end_session'] = True
                else:
                    # если есть неотгаданные города, то продолжаем игру
                    sessionStorage[user_id]['game_started'] = True
                    # номер попытки, чтобы показывать фото по порядку
                    sessionStorage[user_id]['attempt'] = 1
                    # функция, которая выбирает город для игры и показывает фото
                    play_game(res, req)
            elif 'нет' in req['request']['nlu']['tokens']:
                res['response']['text'] = 'Ну и ладно!'
                res['end_session'] = True
            else:
                res['response']['text'] = f'Не поняла ответа, {first_name}! Так да или нет?'
                res['response']['buttons'] = [
                    {
                        'title': 'Да',
                        'hide': True
                    },
                    {
                        'title': 'Нет',
                        'hide': True
                    }
                ]
        else:
            play_game(res, req)


def play_game(res, req):
    user_id = req['session']['user_id']
    first_name = sessionStorage[user_id]['first_name'].title()
    attempt = sessionStorage[user_id]['attempt']
    if attempt == 1:
        # если попытка первая, то случайным образом выбираем город для гадания
        city = random.choice(list(cities))
        # выбираем его до тех пор пока не выбираем город, которого нет в sessionStorage[user_id]['guessed_cities']
        while city in sessionStorage[user_id]['guessed_cities']:
            city = random.choice(list(cities))
        # записываем город в информацию о пользователе
        sessionStorage[user_id]['city'] = city
        # добавляем в ответ картинку
        res['response']['card'] = {}
        res['response']['card']['type'] = 'BigImage'
        res['response']['card']['title'] = f'Что это за город, {first_name}?'
        res['response']['card']['image_id'] = cities[city][attempt - 1]
        res['response']['text'] = f'Тогда сыграем, {first_name}!'
    else:
        # сюда попадаем, если попытка отгадать не первая
        city = sessionStorage[user_id]['city']

        country = get_country(city.title()).lower()

        # если город уже отгадан и мы ждем страну
        if city in sessionStorage[user_id]['guessed_cities']:
            if  country in req['request']['nlu']['tokens']:
                res['response']['text'] = f'Правльно, {first_name}! Сыграем еще?'
            else:
                res['response']['text'] = f'{first_name}, нет, {city.title()} находится в {country.capitalize()}. Сыграем еще?'
            res['response']['buttons'].append(
                {
                    'title': 'Да',
                    'hide': True}
            )
            res['response']['buttons'].append(
                {
                    'title': 'Нет',
                    'hide': True}
            )
            res['response']['buttons'].append(
                {
                    'title': 'Показать этот город на карте',
                    'url': f'https://yandex.ru/maps/?mode=search&text={city.title()}',
                    'hide': True}
            )
            sessionStorage[user_id]['game_started'] = False
            return

        if get_city(req) == city:
            # если да, то добавляем город к sessionStorage[user_id]['guessed_cities'] и
            # отправляем пользователя на второй круг. Обратите внимание на этот шаг на схеме.
            res['response']['text'] = f'Правильно, {first_name}! А в какой стране этот город?'
            sessionStorage[user_id]['guessed_cities'].append(city)
            return

        else:
            # если нет
            if attempt == 3:
                # если попытка третья, то значит, что все картинки мы показали.
                # В этом случае говорим ответ пользователю,
                # добавляем город к sessionStorage[user_id]['guessed_cities'] и отправляем его на второй круг.
                # Обратите внимание на этот шаг на схеме.
                res['response']['text'] = f'{first_name}, вы пытались. Это {city.title()}. Сыграем ещё?'
                sessionStorage[user_id]['game_started'] = False
                sessionStorage[user_id]['guessed_cities'].append(city)
                return
            else:
                # иначе показываем следующую картинку
                res['response']['card'] = {}
                res['response']['card']['type'] = 'BigImage'
                res['response']['card']['title'] = f'{first_name}, неправильно. Вот тебе дополнительное фото'
                res['response']['card']['image_id'] = cities[city][attempt - 1]
                res['response']['text'] = 'А вот и не угадал!'
    # увеличиваем номер попытки доля следующего шага
    sessionStorage[user_id]['attempt'] += 1


def get_city(req):
    # перебираем именованные сущности
    for entity in req['request']['nlu']['entities']:
        # если тип YANDEX.GEO, то пытаемся получить город(city), если нет, то возвращаем None
        if entity['type'] == 'YANDEX.GEO':
            # возвращаем None, если не нашли сущности с типом YANDEX.GEO
            return entity['value'].get('city', None)


def get_first_name(req):
    # перебираем сущности
    for entity in req['request']['nlu']['entities']:
        # находим сущность с типом 'YANDEX.FIO'
        if entity['type'] == 'YANDEX.FIO':
            # Если есть сущность с ключом 'first_name', то возвращаем её значение.
            # Во всех остальных случаях возвращаем None.
            return entity['value'].get('first_name', None)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
