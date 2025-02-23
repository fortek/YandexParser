import asyncio
import json
import pandas as pd
from playwright.async_api import async_playwright

# Глобальный список для накопления найденных данных
found_results = []  # Каждый элемент – словарь с ключами "Organization" и "Phones"

async def main():
    # Событие, которое будет установлено, когда прокрутка завершится
    scroll_finished_event = asyncio.Event()

    async with async_playwright() as p:
        # Запускаем браузер с параметрами для обхода обнаружения автоматизации
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        # Создаем контекст с реальным User Agent
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/115.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        # Открываем страницу Яндекс.Карт
        await page.goto("https://yandex.ru/maps", wait_until="domcontentloaded")
        await asyncio.sleep(1)
        # Закрываем окно с куки, если оно появляется
        try:
            await page.click("button[aria-label='Принять']", timeout=3000)
        except Exception:
            pass

        # Запрашиваем у пользователя поисковый запрос и желаемое количество результатов
        search_query = input("Введите, что искать: ")
        desired_count = int(input("Введите желаемое количество результатов: "))


        # Обработчик для перехвата ответов API Яндекс-Карт
        async def handle_response(response):
            if "https://yandex.ru/maps/api/search?add_type=direct&ajax=1" in response.url:
                try:
                    text = await response.text()
                    print("\nПерехвачен ответ по URL:", response.url)
                    data = json.loads(text)
                    items = data.get("data", {}).get("items", [])
                    if items:
                        for item in items:
                            organization = item.get("title", "Нет названия")
                            phones = item.get("phones", [])
                            phone_numbers = [phone.get("number") for phone in phones if "number" in phone]
                            # Парсим ссылки из поля "urls"
                            urls = item.get("urls", [])
                            website = ", ".join(urls) if urls else ""

                            print(f"Организация: {organization}")
                            if phone_numbers:
                                print("Номера:", ", ".join(phone_numbers))
                            else:
                                print("Номера: не найдены")
                            print(f"Сайт: {website}")
                            print("-" * 40)

                            found_results.append({
                                "Organization": organization,
                                "Phones": ", ".join(phone_numbers) if phone_numbers else "",
                                "Website": website
                            })
                    else:
                        print("Организации не найдены в ответе.")
                except Exception as e:
                    print("Ошибка при обработке ответа:", e)

                # После получения ответа запускаем цикл прокрутки списка заведений
                print("Запускаем прокрутку списка заведений...")
                n = 0
                while True:
                    # Ищем все элементы, соответствующие заведению
                    elements = await page.query_selector_all(".search-business-snippet-view__content")
                    count_before = len(elements)
                    print(f"Элементов до скролла: {count_before}")
                    await asyncio.sleep(1)
                    if count_before > 0:
                        last_element = elements[-1]
                        await last_element.evaluate("el => el.scrollIntoView(true)")
                    await asyncio.sleep(1)
                    elements = await page.query_selector_all(".search-business-snippet-view__content")
                    count_after = len(elements)
                    print(f"Элементов после скролла: {count_after}")
                    # Если достигнуто желаемое количество элементов, завершаем цикл
                    if count_after >= desired_count:
                        print(f"Достигнуто желаемое количество элементов: {count_after}")
                        break
                    # Если число элементов не изменилось, увеличиваем счетчик стабильных итераций
                    if count_before == count_after:
                        n += 1
                        print(f"Стабильно {n} итераций подряд.")
                        if n >= 5:
                            break
                    else:
                        n = 0
                print("Прокрутка завершена.")
                scroll_finished_event.set()

        # Подключаем обработчик к событию "response"
        page.on("response", handle_response)

        # Ждем появления поля поиска и запускаем поиск
        await page.wait_for_selector("input.input__control._bold", state="attached", timeout=5000)
        await page.fill("input.input__control._bold", search_query)
        await page.keyboard.press("Enter")

        # Ждем, пока прокрутка не завершится (через событие scroll_finished_event)
        await scroll_finished_event.wait()
        print("Прокрутка завершена, закрываем браузер.")
        await browser.close()

    # После закрытия браузера сохраняем данные в Excel
    if found_results:
        # Если найденных результатов меньше, чем запрошено – сохраняем все; иначе сохраняем первые desired_count
        to_save = found_results if len(found_results) < desired_count else found_results[:desired_count]
        df = pd.DataFrame(to_save)
        output_file = "results.xlsx"
        df.to_excel(output_file, index=False)
        print(f"Данные сохранены в файл: {output_file}")
    else:
        print("Нет данных для сохранения.")

asyncio.run(main())
