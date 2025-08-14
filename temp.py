# test_sensors.py
import psutil

def test_sensors():
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            print("Найденные сенсоры температуры:")
            for name, entries in temps.items():
                print(f"  {name}:")
                for entry in entries:
                    print(f"    {entry.label or 'N/A'}: {entry.current}°C (high: {entry.high}, critical: {entry.critical})")
        else:
            print("Информация о температуре недоступна (пустой словарь).")
    except AttributeError:
        print("psutil.sensors_temperatures() не поддерживается в этой системе или версии psutil.")
    except Exception as e:
        print(f"Произошла ошибка при получении температуры: {e}")

if __name__ == "__main__":
    test_sensors()