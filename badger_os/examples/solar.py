import badger2040
import urequests
import time
import machine
import badger_os
import jpegdec


display = badger2040.Badger2040()
display.set_update_speed(badger2040.UPDATE_FAST)
jpeg = jpegdec.JPEG(display.display)
TIME_OFFSET = 10 # 11 for Daylight Savings
DEBUG = False
WIDTH, HEIGHT = display.get_bounds()
PADDING = 8
APP_DIR = "/examples"
ICON_DIM = 64
SOLAR_SUN_JPG = "solar-panel-sun.jpg"
SOLAR_NO_SUN_JPG = "solar-panel-no-sun.jpg"
HOME_JPG = "home.jpg"
GRID_JPG = "grid.jpg"
SUNRISE_JPG = "sunrise.jpg"
SUNSET_JPG = "sunset.jpg"
TEXT_SCALE = 0.6

LAT = -37.71442
LONG = 145.08097
OWEATHER_KEY="DUMMY_KEY"
OWEATHER_URL = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LONG}&appid={OWEATHER_KEY}&units=metric"

INVERTER_IP = '192.168.1.90'
INVERTER_URL = f"http://{INVERTER_IP}/solar_api/v1/GetPowerFlowRealtimeData.fcgi"

if badger2040.is_wireless():
    import ntptime
    try:
        display.connect()
        if display.isconnected():
            ntptime.settime()

    except (RuntimeError, OSError) as e:
        print(f"Wireless Error: {e.value}")

rtc = machine.RTC()
badger2040.pico_rtc_to_pcf()

# Global variables
# state = {
#     "sunrise": time.localtime(time.mktime(time.localtime()) - 86400),
#     "sunset": time.localtime(time.mktime(time.localtime()) - 86400)
# }
# badger_os.state_load("solar", state)



def get_inverter_data():
    if DEBUG:
        pv = 1543.32
        load = -2000.23
        grid = -(pv + load)
        return pv, load, grid, current_local_time()

    print(f"Requesting URL: {INVERTER_URL}")
    r = urequests.get(INVERTER_URL)
    j = r.json()
    print("Inverter Data obtained!")
    print(j)

    site = j["Body"]["Data"]["Site"]
    grid = site["P_Grid"]
    load = site["P_Load"]
    pv = site["P_PV"]
    updated = current_local_time()

    r.close()

    return pv, load, grid, updated

def get_weather_data():
    print(f"Requesting URL: {OWEATHER_URL}")
    r = urequests.get(OWEATHER_URL)
    j = r.json()
    print("Weather Data obtained!")
    print(j)

    sunrise_epoch = j["sys"]["sunrise"] + (TIME_OFFSET * 3600)
    sunset_epoch = j["sys"]["sunset"] + (TIME_OFFSET * 3600)
    weather = j["weather"][0]["main"]
    temp = j["main"]["temp"]
    humidity = j["main"]["humidity"]
    sunrise = time.localtime(sunrise_epoch)
    sunset = time.localtime(sunset_epoch)

    return sunrise, sunset, weather, temp, humidity

def current_local_time():
    epoch = time.mktime(time.localtime())
    epoch_offset = epoch + (TIME_OFFSET * 3600)

    return time.localtime(epoch_offset)

def is_midnight():
    hour = current_local_time()[3]
    return hour == 0

def format_power(p):
    if p:
        abs_p = abs(p)
        if abs_p < 1000:
            return "{:.0f}W".format(abs_p)
        else:
            return "{:.2f}kW".format(abs_p / 1000)
    else:
        return "0W"

def tuple_to_time(tup):
    hour = tup[3]
    minute = tup[4]
    meridian = "AM" if hour < 12 else "PM"
    hour12 = hour if hour <= 12 else hour - 12
    if hour12 == 0:
        hour12 = 12

    return "{:02d}:{:02d} {}".format(hour12, minute, meridian)

def clean_rectangle(x, y, w, h):
    print(f"Cleaning Coords: x:{x}, y:{y}, w:{w}, h:{h}")
    display.set_pen(15)
    display.rectangle(x, y, w, h)
    display.set_pen(0)

def draw_ui():
    display.set_pen(15)
    display.clear()

    jpeg.open_file(f"{APP_DIR}/{SOLAR_NO_SUN_JPG}")
    jpeg.decode(PADDING, PADDING, jpegdec.JPEG_SCALE_FULL, dither=False)

    jpeg.open_file(f"{APP_DIR}/{HOME_JPG}")
    centered = int((WIDTH/2) - (ICON_DIM/2))
    jpeg.decode(centered, PADDING, jpegdec.JPEG_SCALE_FULL, dither=False)

    jpeg.open_file(f"{APP_DIR}/{GRID_JPG}")
    right_edge = WIDTH - PADDING - ICON_DIM
    jpeg.decode(right_edge, PADDING, jpegdec.JPEG_SCALE_FULL, dither=False)

    width = display.measure_text("...", TEXT_SCALE)
    pv_start = int(PADDING + (ICON_DIM/2) - (width))
    load_start = int((WIDTH/2) - (width))
    grid_start = int(WIDTH - PADDING - (ICON_DIM/2) - (width))

    y_position = 88
    display.set_pen(0)
    display.set_font("sans")
    display.set_thickness(2)
    display.text("...", pv_start, y_position, 0, TEXT_SCALE)
    display.text("...", load_start, y_position, 0, TEXT_SCALE)
    display.text("...", grid_start, y_position, 0, TEXT_SCALE)

    display.set_pen(0)
    display.set_font("bitmap8")
    display.text("Weather", PADDING + 100, HEIGHT - 18, scale=1)
    display.text("...", PADDING + 100, HEIGHT - 8, scale=1.1)

    display.text("Temp", PADDING + 150, HEIGHT - 18, scale=1)
    display.text("...", PADDING + 150, HEIGHT - 8, scale=1.1)

    display.text("Humidity", PADDING + 180, HEIGHT - 18, scale=1)
    display.text("...", PADDING + 180, HEIGHT - 8, scale=1.1)

    display.text("Sunrise", PADDING, HEIGHT - 18, scale=1)
    display.text("...", PADDING, HEIGHT - 8, scale=1.1)

    display.text("Sunset", PADDING + 50, HEIGHT - 18, scale=1)
    display.text("...", PADDING + 50, HEIGHT - 8, scale=1.1)

    display.text("Updated", WIDTH - PADDING - 40, HEIGHT - 18, scale=1)
    display.text("...", WIDTH - PADDING - 40, HEIGHT - 8, scale=1.1)

    display.update()

def update_pv_icon(pv):
    if (state["pv"] == 0 and pv == 0) or (state["pv"] > 0 and pv > 0):
        return
    print("update pv icon")
    pv_icon_region = [PADDING, PADDING, ICON_DIM, ICON_DIM]
    clean_rectangle(*pv_icon_region)
    if pv == 0:
        jpeg.open_file(f"{APP_DIR}/{SOLAR_NO_SUN_JPG}")
    else:
        jpeg.open_file(f"{APP_DIR}/{SOLAR_SUN_JPG}")
    jpeg.decode(PADDING, PADDING, jpegdec.JPEG_SCALE_FULL, dither=False)


    display.partial_update(*pv_icon_region)

def update_power(pv, load, grid):
    print('Update: POWER')
    pv_text = format_power(pv)
    load_text = format_power(load)
    grid_text = format_power(grid)
    pv_width = display.measure_text(pv_text, TEXT_SCALE)
    load_width = display.measure_text(load_text, TEXT_SCALE)
    grid_width = display.measure_text(grid_text, TEXT_SCALE)

    pv_start = int(PADDING + (ICON_DIM/2) - (pv_width))
    load_start = int((WIDTH/2) - (load_width))
    grid_start = int(WIDTH - PADDING - (ICON_DIM/2) - (grid_width))

    y_position = 88
    power_region = [0, y_position - 8, WIDTH, 16]
    clean_rectangle(*power_region)

    display.set_font("sans")
    display.set_thickness(2)

    display.text(pv_text, pv_start, y_position, 0, TEXT_SCALE)
    display.text(load_text, load_start, y_position, 0, TEXT_SCALE)
    display.text(grid_text, grid_start, y_position, 0, TEXT_SCALE)

    display.partial_update(*power_region)

def update_arrows(pv, load, grid):
    print('Update: Arrows')
    arrow_y_pos = int(PADDING + (ICON_DIM * 3/4))

    # PV
    pv_start = int(PADDING + ICON_DIM + PADDING)
    pv_end = int((WIDTH/2) - (ICON_DIM/2) - PADDING)
    grid_start = int((WIDTH/2) + (ICON_DIM/2) + PADDING)
    grid_end = int(WIDTH - PADDING - ICON_DIM - PADDING)

    pv_arrow_region = [pv_start, arrow_y_pos - 8, pv_end - pv_start, 16]
    grid_arrow_region = [grid_start, arrow_y_pos - 8, grid_end - grid_start, 16]

    if pv > 0 and state["pv"] == 0:
        clean_rectangle(*pv_arrow_region)
        display.line(pv_start, arrow_y_pos, pv_end, arrow_y_pos, 2)
        display.triangle(
            pv_end, arrow_y_pos,
            pv_end - 8, arrow_y_pos + 6,
            pv_end - 8, arrow_y_pos - 6
        )
        display.partial_update(*pv_arrow_region)

    if pv == 0 and state["pv"] > 0:
        clean_rectangle(*pv_arrow_region)
        display.partial_update(*pv_arrow_region)

    if grid > 0 and state["grid"] <= 0:
        clean_rectangle(*grid_arrow_region)
        display.line(grid_start, arrow_y_pos, grid_end, arrow_y_pos, 2)
        display.triangle(
            grid_start, arrow_y_pos,
            grid_start + 8, arrow_y_pos + 6,
            grid_start + 8, arrow_y_pos - 6
        )
        display.partial_update(*grid_arrow_region)

    elif grid < 0 and state["grid"] >= 0:
        clean_rectangle(*grid_arrow_region)
        display.line(grid_start, arrow_y_pos, grid_end, arrow_y_pos, 2)
        display.triangle(
            grid_end, arrow_y_pos,
            grid_end - 8, arrow_y_pos + 6,
            grid_end - 8, arrow_y_pos - 6
        )
        display.partial_update(*grid_arrow_region)

    elif grid == 0:
        clean_rectangle(*grid_arrow_region)
        display.partial_update(*grid_arrow_region)

def draw_sun(sunrise, sunset):
    display.set_font("bitmap8")

    if sunrise != state["sunrise"]:
        print('Update: Sunrise')

        sunrise_region = [PADDING, HEIGHT - 8, 40, 8]
        clean_rectangle(*sunrise_region)

        display.text(tuple_to_time(sunrise), PADDING, HEIGHT - 8, scale=1.1)

        display.partial_update(*sunrise_region)

    if sunset != state["sunset"]:
        print('Update: sunset')

        sunset_region = [PADDING + 50, HEIGHT - 8, 40, 8]
        clean_rectangle(*sunset_region)

        display.text(tuple_to_time(sunset), PADDING + 50, HEIGHT - 8, scale=1.1)

        display.partial_update(*sunset_region)

def draw_weather(weather, temp, humidity):
    if weather != state["weather"]:
        print('Update: Weather')

        weather_region = [PADDING + 100, HEIGHT - 8, 30, 8]
        clean_rectangle(*weather_region)

        display.text(weather, PADDING + 100, HEIGHT - 8, scale=1.1)

        display.partial_update(*weather_region)

    if temp != state["temp"]:
        print('Update: Temp')

        temp_region = [PADDING + 150, HEIGHT - 8, 20, 8]
        clean_rectangle(*temp_region)

        temp_format = "{:.0f}°C".format(temp)
        display.text(temp_format, PADDING + 150, HEIGHT - 8, scale=1.1)

        display.partial_update(*temp_region)

    if humidity != state["humidity"]:
        print('Update: Humidity')

        humidity_region = [PADDING + 180, HEIGHT - 8, 50, 8]
        clean_rectangle(*humidity_region)

        humidity_format = "{:.0f}%".format(humidity)
        display.text(humidity_format, PADDING + 180, HEIGHT - 8, scale=1.1)

        display.partial_update(*humidity_region)

def draw_updated(tup):
    print('Update: updated')

    updated_region = [WIDTH - PADDING - 40, HEIGHT - 8, 45, 8]
    clean_rectangle(*updated_region)

    display.set_font("bitmap8")
    display.text(tuple_to_time(tup), WIDTH - PADDING - 40, HEIGHT - 8, scale=1.1)

    display.partial_update(*updated_region)

def update_state(pv, load, grid, weather, temp, humidity, sunrise, sunset):
    state["pv"] = pv
    state["load"] = load
    state["grid"] = grid
    state["weather"] = weather
    state["temp"] = temp
    state["humidity"] = humidity
    state["sunrise"] = sunrise
    state["sunset"] = sunset

state = {
    "counter": 0,
    "sunrise": time.localtime(),
    "sunset": time.localtime(),
    "pv": 0,
    "load": 0,
    "grid": 0,
    "weather": 0,
    "temp": 0,
    "humidity": 0
}

draw_ui()
while True:
    print("Refreshing...")
    display.led(128)
    print(state)
    pv, load, grid, updated_at = get_inverter_data()

    if state["counter"] <= 0:
        sunrise, sunset, weather, temp, humidity = get_weather_data()
        state["counter"] = 30
    else:
        sunrise = state["sunrise"]
        sunset = state["sunset"]
        weather = state["weather"]
        temp = state["temp"]
        humidity = state["humidity"]

    update_pv_icon(pv)
    update_power(pv, load, grid)
    update_arrows(pv, load, grid)
    draw_sun(sunrise, sunset)
    draw_weather(weather, temp, humidity)
    draw_updated(updated_at)

    update_state(pv, load, grid, weather, temp, humidity, sunrise, sunset)
    state["counter"] -= 1
    display.led(0)

    time.sleep(30)
