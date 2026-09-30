import random
import os
import time
import msvcrt


# Instellingen
LANES = 3
ROAD_HEIGHT = 12

# Speler
player_lane = 1
player_row = ROAD_HEIGHT - 2

# Tegenstanders
cars = []
recent_car_lanes = []

score = 0
game_over = False


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def create_car():
    available_lanes = list(range(LANES))

    if len(recent_car_lanes) == 2 and recent_car_lanes[0] != recent_car_lanes[1]:
        blocked_lane = next(
            lane for lane in available_lanes
            if lane not in recent_car_lanes
        )
        available_lanes.remove(blocked_lane)

    lane = random.choice(available_lanes)
    row = 0

    cars.append({
        "lane": lane,
        "row": row
    })
    recent_car_lanes.append(lane)
    del recent_car_lanes[:-2]


def move_cars():
    for car in cars:
        car["row"] += 1


def remove_cars():
    global score

    remaining_cars = []

    for car in cars:
        if car["row"] >= ROAD_HEIGHT:
            score += 1
        else:
            remaining_cars.append(car)

    cars.clear()
    cars.extend(remaining_cars)


def check_collision():
    for car in cars:
        if car["lane"] == player_lane and car["row"] == player_row:
            return True

    return False


def draw_road():
    clear_screen()

    print("=" * 25)
    print("       🏁 RACE GAME")
    print("=" * 25)
    print(f"Score: {score}")
    print()
    print("A = links | D = rechts | Q = stoppen")
    print()

    # Bovenkant van de weg
    print("+---+---+---+")

    for row in range(ROAD_HEIGHT):

        line = "|"

        for lane in range(LANES):

            symbol = " "

            # Speler
            if lane == player_lane and row == player_row:
                symbol = "🚗 "

            # Tegenstanders
            for car in cars:
                if car["lane"] == lane and car["row"] == row:
                    symbol = "🚙 "

            # Zorg dat de rijbaan 3 tekens breed blijft
            if symbol == " ":
                line += "   |"
            else:
                line += f"{symbol}|"

        print(line)

    print("+---+---+---+")


def move_player(command):
    global player_lane

    if command == "a":
        if player_lane > 0:
            player_lane -= 1

    elif command == "d":
        if player_lane < LANES - 1:
            player_lane += 1


def read_command():
    if msvcrt.kbhit():
        return msvcrt.getwch().lower()

    return ""


def game_loop():
    global game_over

    while not game_over:

        draw_road()

        command = read_command()

        if command == "q":
            game_over = True
            break

        move_player(command)

        # Botsing controleren voordat tegenstanders bewegen
        if check_collision():
            game_over = True
            break

        # Auto's bewegen
        move_cars()

        # Soms komt er een nieuwe auto
        if random.randint(1, 100) <= 50:
            create_car()

        # Botsing controleren
        if check_collision():
            game_over = True

        remove_cars()

        time.sleep(0.2)

    clear_screen()

    print("=" * 25)
    print("       💥 CRASH!")
    print("=" * 25)


    print()
    print(f"🏁 Eindscore: {score}")
    print()
    print("Bedankt voor het spelen!")


def main():
    game_loop()


if __name__ == "__main__":
    main()
