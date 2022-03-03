import argparse
import base64
import json
import cv2
import numpy as np
import requests
from loguru import logger
from lxml import html
from requests import Response

from settings import captcha_url, headers, found_result, not_found_result, error_captcha, url_main, fake_mail, \
    result_false, result_false_captcha, result_not_found, result_found, format_error


class MVDParser(object):
    """
    Создаем объект для получения данных из сайта мвд.рф
    """

    def __init__(self, session: requests.sessions, s_surname: str, s_name: str, s_year: str, s_month: str = None,
                 s_day: str = None, s_secondname: str = None):
        self.session = session

        self.s_surname = s_surname
        self.s_name = s_name
        self.s_secondname = s_secondname
        self.s_year = s_year
        self.s_month = s_month
        self.s_day = s_day

    def get_captcha(self) -> str:
        """
        Получаем изображение captcha для ручного ввода
        """
        resp = self.session.get(captcha_url, headers=headers, stream=True).raw
        image_captcha = np.asarray(bytearray(resp.read()), dtype="uint8")
        image = cv2.imdecode(image_captcha, cv2.IMREAD_COLOR)
        ## Выводим изображение с капчей
        cv2.imshow('image', image)
        ## Ждем пока юзер догадается нажать на кнопку, чтобы изображение скрылось
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        captcha = input('Введите данные из изображения:\n')
        return captcha

    def forming_query(self, captcha: str) -> str:
        """
        Формирование запроса из введенных данных
        """
        url = f'https://{url_main}?s_family={self.s_surname}&fio={self.s_name}&d_year={self.s_year}'
        if self.s_secondname:
            url += f'&s_patr={self.s_secondname}'
        if self.s_month:
            url += f'&d_month={self.s_month}'
            ## только если есть месяц добавляем день
            if self.s_day:
                url += f'&d_day={self.s_day}'
        url += f'&email={fake_mail}&captcha={captcha}'
        return url

    def get_result_from_site(self, url: str) -> Response:
        """
        Получение результата с сайта
        """
        return self.session.get(url, headers=headers)

    def get_json(self, result: Response) -> dict:
        """
        Проверка информаци и формирование итогового словаря
        """
        if found_result in result.text:
            logger.info(result_found)
            tree = html.fromstring(result.content)
            img = tree.xpath('/html/body/div[1]/div/div[5]/div[2]/div[5]/div[1]/div[2]/div/div/div[1]/img')
            url = 'http:' + img[0].attrib['src']
            base_str = get_image_as_base64(url)
            return {"result": "success", "exists": True, "photo_b64": base_str}
        elif not_found_result in result.text:
            logger.info(result_not_found)
            return {"result": "success", "exists": False, "photo_b64": ''}
        elif error_captcha in result.text:
            logger.error(result_false_captcha)
            return {"result": "error", "message": result_false_captcha}
        else:
            logger.error(result_false)
            return {"result": "error", "message": result_false}


def get_image_as_base64(url: str) -> str:
    """
    Получение base64 картинки по url
    """
    return base64.b64encode(requests.get(url).content).decode('utf-8')


def main():
    session = requests.Session()
    s_surname, s_name, s_year, s_month, s_day, s_secondname = None, None, None, None, None, None

    parser = argparse.ArgumentParser(description="Получение информации о федеральном розыске по ФИО")
    parser.add_argument('fio', type=str, help="ФИО")
    parser.add_argument('birthday', type=str, help="Дата рождения. Формат: YYYY, dd.MM.YYYY")
    args = parser.parse_args()

    split_fio = args.fio.split(' ')
    if len(split_fio) == 2:
        [s_surname, s_name] = split_fio
    elif len(split_fio) == 3:
        [s_surname, s_name, s_secondname] = split_fio
    else:
        logger.error(f'{format_error}: ФИО')
        exit()

    split_date = args.birthday.split('.')
    if len(split_date) == 1:
        s_year = split_date[0]
    elif len(split_date) == 3:
        [s_year, s_month, s_day] = split_date[0], split_date[1], split_date[2]
    else:
        logger.error(f'{format_error}: Дата')
        exit()

    parser = MVDParser(
        session=session, s_surname=s_surname, s_name=s_name, s_secondname=s_secondname, s_year=s_year, s_month=s_month,
        s_day=s_day,
    )
    captcha = parser.get_captcha()
    url = parser.forming_query(captcha)
    res_ = parser.get_result_from_site(url)
    json_ = parser.get_json(res_)
    with open('result.json', 'w') as f:
        json.dump(json_, f)


if __name__ == '__main__':
    main()
