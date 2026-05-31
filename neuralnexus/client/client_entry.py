"""
client_entry.py
---------------
NeuralNexus CLI client entry point.

Discovers the current Raft leader, establishes gRPC connections to all
service stubs, then launches the main menu.

Usage (from the client/ directory with the virtual environment activated):
    python client_entry.py
"""

import time

from rpc_client import (
    LEADER_RETRY_DELAY,
    get_leader_id,
    get_leader_host_port,
    connect_to_leader,
)
from menu_renderer import handle_menu
from ui_actions import MAIN_MENU_OPTIONS, MAIN_MENU_ACTIONS


def main() -> None:
    print("=" * 55)
    print("  NeuralNexus – Distributed AI Learning Platform")
    print("=" * 55)

    while True:
        leader_id = get_leader_id()

        if leader_id:
            host, port = get_leader_host_port(leader_id)
            if host and port:
                channel = connect_to_leader(host, port)
                if channel:
                    handle_menu(MAIN_MENU_OPTIONS, MAIN_MENU_ACTIONS, "Main Menu")
                    break
            else:
                print("[NeuralNexus] Leader not found in node list, retrying...")
        else:
            print("[NeuralNexus] No leader found, retrying...")

        time.sleep(LEADER_RETRY_DELAY)


if __name__ == "__main__":
    main()
