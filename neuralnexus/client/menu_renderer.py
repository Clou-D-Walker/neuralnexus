"""
menu_renderer.py
----------------
Generic recursive menu renderer for the NeuralNexus CLI client.
"""


def handle_menu(options: tuple, actions: dict, head: str) -> None:
    """
    Display a numbered menu, read user input, and dispatch to the
    appropriate action function.

    Each action function should return ``(further_menu_dict | None, terminate_bool)``.
    If *further_menu_dict* is not None, ``handle_menu`` is called recursively.
    If *terminate_bool* is True, the current menu exits.
    """
    while True:
        print(f"\n==== {head} ====")
        valid_ids = []
        for option_id, option_name in options:
            valid_ids.append(option_id)
            print(f"[{option_id}] {option_name}")
        print("[0] Back / Exit")

        try:
            choice = int(input("Select an option: "))
        except ValueError:
            print("Please enter a valid number.")
            continue

        if choice == 0:
            print("Going back...")
            return

        if choice not in valid_ids:
            print("Invalid option. Please try again.")
            continue

        action = actions.get(choice)
        if not action:
            print("Invalid option. Please try again.")
            continue

        further_menu, terminate = action()
        if terminate:
            print("Exiting...")
            return
        if further_menu:
            handle_menu(**further_menu)
