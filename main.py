import json
import os
import pickle
import platform
import re
import sys
import time

from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException

driver_url = os.path.abspath('geckodriver')

if platform.system() == 'Windows':
    driver_url = os.path.abspath('windows/geckodriver.exe')

url = 'https://steamcommunity.com/'
COOKIES_FILE = 'cookies'

load_dotenv('config.env')

if not (os.environ.get('USERNAME_STEAM') and os.environ.get('PASSWORD_STEAM')):
    print('Steam username and steam password not found')
    sys.exit()


class SteamBot:
    """ Steam bot """

    def __init__(self) -> None:
        self._options = webdriver.FirefoxOptions()
        self._options.headless = True
        self._driver = webdriver.Firefox(executable_path=fr'{driver_url}', options=self._options)
        self._username = os.environ.get('USERNAME_STEAM', 'USERNAME_STEAM')
        self._password = os.environ.get('PASSWORD_STEAM', 'PASSWORD_STEAM')

    def close_browser(self) -> None:
        """ Close browser """

        self._driver.close()
        self._driver.quit()

    def xpath_exist(self, xpath: str) -> bool:
        """ Element with xpath exist? """

        try:
            self._driver.find_element_by_xpath(xpath)
            return True
        except NoSuchElementException:
            return False

    def login(self) -> None:
        """ Login in Steam """

        driver = self._driver
        driver.get(url)
        driver.implicitly_wait(5)

        if os.path.exists(COOKIES_FILE):
            self.set_cookies()
            driver.refresh()
            driver.implicitly_wait(5)
            driver.find_element_by_class_name('user_avatar').click()
            return

        driver.find_element_by_class_name('global_action_link').click()
        driver.implicitly_wait(5)

        username = driver.find_element_by_xpath('//input[@id="input_username"]')
        username.clear()
        username.send_keys(self._username)
        password = driver.find_element_by_xpath('//input[@id="input_password"]')
        password.clear()
        password.send_keys(self._password)
        driver.implicitly_wait(3)

        driver.find_element_by_xpath('//button[@type="submit"]').click()
        driver.implicitly_wait(5)

        # 2-step auth
        if self.xpath_exist('//input[@id="twofactorcode_entry"]'):
            code = input('Please input 2-factor code: ')
            if driver.find_element_by_xpath('//input[@id="twofactorcode_entry"]').is_displayed():
                code_otp = driver.find_element_by_xpath('//input[@id="twofactorcode_entry"]')
                code_otp.clear()
                code_otp.send_keys(code)
                driver.implicitly_wait(2)
                driver.find_element_by_id('login_twofactorauth_buttonset_entercode') \
                    .find_element_by_class_name('leftbtn').click()
            else:
                code_otp = driver.find_element_by_xpath('//input[@id="authcode"]')
                code_otp.clear()
                code_otp.send_keys(code)
                driver.implicitly_wait(2)
                driver.find_element_by_id('auth_buttonset_entercode') \
                    .find_element_by_class_name('leftbtn').click()
                time.sleep(3)
                driver.find_element_by_css_selector('[data-modalstate="complete"]').click()

            driver.implicitly_wait(15)

        driver.find_element_by_class_name('user_avatar').click()
        self.save_cookies()

    def save_cookies(self) -> None:
        """ Save cookies """

        with open(COOKIES_FILE, 'wb') as file:
            pickle.dump(self._driver.get_cookies(), file)

    def set_cookies(self) -> None:
        """ Set cookies """

        with open(COOKIES_FILE, 'rb') as file:
            for cookie in pickle.load(file):
                self._driver.add_cookie(cookie)

    def inventory(self) -> list[dict[str, str]]:
        """ Inventory """

        driver = self._driver
        driver.maximize_window()

        driver.implicitly_wait(5)
        driver.get(driver.current_url + 'inventory')
        driver.implicitly_wait(5)

        # Select game for sell items
        games = driver.find_elements_by_xpath('//span[@class="games_list_tab_name"]')
        for i in range(len(games)):
            print(f'{i + 1} - {games[i].text}')
        while True:
            select_game = input('Select game for sell items: ')
            if select_game.isdigit():
                select_game = int(select_game)
                if 0 < select_game <= len(games):
                    break
        current_game = select_game - 1
        games[current_game].click()
        driver.implicitly_wait(5)

        # If not sold items
        driver.find_element_by_id('filter_tag_show').click()
        driver.implicitly_wait(3)
        if not self.xpath_exist('//input[@tag_name="marketable"]'):
            raise ValueError('The game has no items to sell')

        marketable_count = driver.find_element_by_xpath(
            '//div[./input[@tag_name="marketable"]]/label[@class="econ_tag_filter_label"]/span[@class="econ_tag_count"]'
        ).text
        count = int(re.findall('\d+', marketable_count)[0])
        driver.refresh()
        sold_items = []

        for i in range(count):
            driver.find_element_by_id('filter_tag_show').click()
            driver.implicitly_wait(3)
            driver.find_element_by_xpath('//input[@tag_name="marketable"]').click()
            time.sleep(3)

            for item in driver.find_elements_by_class_name('itemHolder'):
                # Only sold items
                if item.is_displayed():
                    item.click()
                    time.sleep(5)

                    price_block = driver.find_elements_by_css_selector(
                        'div#iteminfo0_item_market_actions > div > div'
                    )[1].text
                    name = driver.find_element_by_id('iteminfo0_item_name').text
                    # If no one sells item
                    try:
                        price = re.findall('\d+\,\d+', price_block)[0]
                    except IndexError:
                        continue
                    driver.implicitly_wait(3)

                    # If price item > 45 rub
                    if float(price.replace(',', '.')) > 45:
                        continue

                    driver.find_element_by_class_name('item_market_action_button_contents').click()
                    driver.implicitly_wait(5)

                    input_market_price = driver.find_element_by_id('market_sell_buyercurrency_input')
                    input_market_price.clear()
                    input_market_price.send_keys(price)

                    checkbox = driver.find_element_by_css_selector('input#market_sell_dialog_accept_ssa')
                    if not checkbox.get_attribute('checked'):
                        checkbox.click()

                    driver.implicitly_wait(3)
                    driver.find_element_by_css_selector('a#market_sell_dialog_accept').click()
                    driver.implicitly_wait(3)

                    if self.xpath_exist('//*[@id="market_sell_dialog_ok"]'):
                        driver.find_element_by_xpath('//*[@id="market_sell_dialog_ok"]').click()
                    driver.refresh()
                    sold_items.append({'name': name, 'price': f'{price} rub'})
                    time.sleep(5)
                    break
        return sold_items

    @staticmethod
    def save_json(data: list[dict[str, str]]) -> None:
        """ Save result to json file """

        with open('result.json', 'w') as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

    def run(self) -> None:
        """ Start bot """

        try:
            self.login()
            sold_items = self.inventory()
            self.save_json(sold_items)
            print('Success! Check file result.json for detail sold')
        except Exception as _ex:
            print(_ex)
        finally:
            self.close_browser()


if __name__ == '__main__':
    bot = SteamBot()
    bot.run()
