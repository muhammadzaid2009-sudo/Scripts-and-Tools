"""
Enhanced Python Pentester Toolkit

A menu-driven toolkit that integrates multithreaded subdomain enumeration,
directory enumeration, and port scanning with banner grabbing.

Usage:
    python toolkit.py
"""

import concurrent.futures
import requests
import socket
import sys

DEFAULT_THREADS = 20
DEFAULT_TIMEOUT = 1.0


# ----- Helper / Shared Utilities -----

def load_wordlist(filepath):
    """Read a wordlist file and return a list of stripped lines."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            words = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        print(f"[*] Loaded {len(words)} entries from {filepath}")
        return words
    except FileNotFoundError:
        print(f"[!] Error: '{filepath}' not found.")
        return []


def resolve_target(target):
    """Resolve a hostname to an IP address."""
    try:
        ip = socket.gethostbyname(target)
        if ip != target:
            print(f"[*] Resolved {target} -> {ip}")
        return ip
    except socket.gaierror:
        print(f"[!] Could not resolve {target}")
        return None


# ----- Subdomain Enumeration -----

def _check_subdomain(sub, domain):
    fqdn = f"{sub}.{domain}"
    try:
        ip = socket.gethostbyname(fqdn)
        return fqdn, ip
    except socket.gaierror:
        return None


def enumerate_subdomains(domain, wordlist, max_workers=DEFAULT_THREADS):
    """Test subdomain candidates using concurrent DNS lookups."""
    found = []
    print(f"[*] Enumerating subdomains with {max_workers} threads...\n")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_check_subdomain, sub, domain): sub for sub in wordlist}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                fqdn, ip = res
                print(f"[+] Found: {fqdn} ({ip})")
                found.append(res)
    return found


# ----- Directory Enumeration -----

def _check_directory(session, base_url, entry, extension):
    url = f"{base_url.rstrip('/')}/{entry}{extension}"
    try:
        r = session.get(url, timeout=3, allow_redirects=False)
        if r.status_code not in (404, 400):
            return url, r.status_code, len(r.content)
    except requests.RequestException:
        pass
    return None


def enumerate_directories(target_url, wordlist, extension="", max_workers=DEFAULT_THREADS):
    """Test directory/file candidates concurrently using requests.Session."""
    found = []
    print(f"[*] Enumerating directories with {max_workers} threads...\n")

    session = requests.Session()
    session.headers.update({"User-Agent": "SecurityToolkit/2.0"})

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_check_directory, session, target_url, entry, extension): entry
            for entry in wordlist
        }
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                url, status_code, length = res
                print(f"[+] [{status_code}] {url} (size: {length} B)")
                found.append(res)
    return found


# ----- Port Scanning & Banner Grabbing -----

COMMON_SERVICES = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
    80: "HTTP", 110: "POP3", 139: "NetBIOS", 443: "HTTPS", 445: "SMB",
    1433: "MSSQL", 3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL",
    8080: "HTTP-Proxy", 8443: "HTTPS-Alt"
}


def grab_banner(ip, port, timeout=DEFAULT_TIMEOUT):
    """Attempt to grab a service banner on an open port."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))
        if port in (80, 8080):
            sock.sendall(b"HEAD / HTTP/1.1\r\nHost: target\r\n\r\n")
        banner = sock.recv(1024).decode("utf-8", errors="ignore").strip()
        sock.close()
        return banner.split("\n")[0] if banner else ""
    except (socket.error, socket.timeout):
        return ""


def _probe_port(ip, port, timeout=DEFAULT_TIMEOUT):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        if result == 0:
            banner = grab_banner(ip, port, timeout)
            return port, banner
    except socket.error:
        pass
    return None


def scan_ports(ip, port_list, max_workers=50, timeout=DEFAULT_TIMEOUT):
    """Scan a collection of ports concurrently."""
    open_ports = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_probe_port, ip, p, timeout): p for p in port_list}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                port, banner = res
                service = COMMON_SERVICES.get(port, "Unknown")
                banner_str = f" | Banner: {banner}" if banner else ""
                print(f"[+] Port {port:<5} OPEN ({service}){banner_str}")
                open_ports.append(res)
    return open_ports


def parse_port_input(port_input):
    """Parse port strings like '80', '1-1024', or '22,80,443'."""
    ports = set()
    for part in port_input.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            ports.update(range(int(start), int(end) + 1))
        elif part.isdigit():
            ports.add(int(part))
    return sorted(p for p in ports if 1 <= p <= 65535)


# ----- Toolkit Menu Functions -----

def run_subdomain_enum():
    domain = input("Enter target domain (e.g. example.com): ").strip()
    wordlist_path = input("Enter wordlist path: ").strip()
    wordlist = load_wordlist(wordlist_path)
    if not wordlist:
        return

    results = enumerate_subdomains(domain, wordlist)
    print(f"\n[*] Found {len(results)} subdomain(s).")


def run_directory_enum():
    target_url = input("Enter target URL (e.g., http://10.10.10.5:8080): ").strip()
    if not target_url.startswith(("http://", "https://")):
        target_url = "http://" + target_url

    wordlist_path = input("Enter wordlist path: ").strip()
    extension = input("Enter file extension to append (leave empty for none, e.g. .html): ").strip()

    wordlist = load_wordlist(wordlist_path)
    if not wordlist:
        return

    results = enumerate_directories(target_url, wordlist, extension)
    print(f"\n[*] Found {len(results)} valid path(s).")


def run_port_scan():
    target = input("Enter target IP or hostname: ").strip()
    port_input = input("Enter ports/range (e.g. 1-1024, 80,443,8080) [default: 1-1024]: ").strip() or "1-1024"

    try:
        ports = parse_port_input(port_input)
    except ValueError:
        print("[!] Invalid port format.")
        return

    if not ports:
        print("[!] No valid ports to scan.")
        return

    ip = resolve_target(target)
    if not ip:
        return

    print(f"\n[*] Scanning {ip} ({len(ports)} ports)...\n")
    open_ports = scan_ports(ip, ports)

    if not open_ports:
        print("[!] No open ports found.")
    else:
        print(f"\n[*] Scan complete. Found {len(open_ports)} open port(s).")


def show_menu():
    print("\n" + "=" * 44)
    print("      Python Pentester Toolkit v2.0")
    print("=" * 44)
    print("  1. Subdomain Enumeration (DNS)")
    print("  2. Directory / File Enumeration")
    print("  3. Port Scanner & Banner Grabber")
    print("  4. Exit")
    print("=" * 44)


def main():
    actions = {
        "1": run_subdomain_enum,
        "2": run_directory_enum,
        "3": run_port_scan,
    }

    while True:
        try:
            show_menu()
            choice = input("\nSelect an option [1-4]: ").strip()

            if choice == "4":
                print("[*] Exiting toolkit. Goodbye.")
                break
            elif choice in actions:
                print()
                actions[choice]()
            else:
                print("[!] Invalid option. Enter 1-4.")
        except KeyboardInterrupt:
            print("\n\n[!] Operation cancelled by user.")
            break


if __name__ == "__main__":
    main()
