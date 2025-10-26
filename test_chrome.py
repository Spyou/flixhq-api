from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time

chrome_options = Options()
# headless=False means Chrome WILL appear
# Don't add --headless argument

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=chrome_options
)

print("Chrome should be open now!")
driver.get("https://www.google.com")
time.sleep(5)  # Wait 5 seconds so you can see it
driver.quit()
print("Chrome closed")
