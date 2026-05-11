"""
scenarios.py – Definicje 24 scenariuszy testowych.

Każdy scenariusz ma:
  - id         : numer 1-24
  - operation  : CREATE / READ / UPDATE / DELETE
  - name       : krótka nazwa
  - description: opis co testuje
  - json_related: czy dotyczy danych półustrukturalnych (JSON)
"""

SCENARIOS = [
    # CREATE (1-6)
    {
        "id": 1,
        "operation": "CREATE",
        "name": "Wstaw 1 użytkownika",
        "description": "INSERT pojedynczego rekordu do tabeli users",
        "json_related": False,
    },
    {
        "id": 2,
        "operation": "CREATE",
        "name": "Wstaw 100 użytkowników wsadowo",
        "description": "Bulk INSERT 100 rekordów users naraz",
        "json_related": False,
    },
    {
        "id": 3,
        "operation": "CREATE",
        "name": "Wstaw event z danymi JSON",
        "description": "INSERT eventu z polem additional_info (JSON): age_limit, parking, languages",
        "json_related": True,
    },
    {
        "id": 4,
        "operation": "CREATE",
        "name": "Wstaw booking z platnoscia",
        "description": "INSERT bookingu + 1 pozycja biletu + 1 platnosc",
        "json_related": False,
    },
    {
        "id": 5,
        "operation": "CREATE",
        "name": "Wstaw recenzje eventu",
        "description": "INSERT pojedynczej recenzji user-event",
        "json_related": False,
    },
    {
        "id": 6,
        "operation": "CREATE",
        "name": "Wstaw bilet powiazany z eventem",
        "description": "INSERT pojedynczego biletu powiazanego z eventem i strefa",
        "json_related": False,
    },

    # READ (7-12)
    {
        "id": 7,
        "operation": "READ",
        "name": "SELECT user po emailu",
        "description": "Wyszukanie użytkownika po email (kolumna z indeksem)",
        "json_related": False,
    },
    {
        "id": 8,
        "operation": "READ",
        "name": "SELECT eventy po statusie i dacie",
        "description": "Filtrowanie eventow po statusie i zakresie start_date",
        "json_related": False,
    },
    {
        "id": 9,
        "operation": "READ",
        "name": "SELECT booking z JOINami",
        "description": "Złączenie booking + booking_tickets + tickets + events",
        "json_related": False,
    },
    {
        "id": 10,
        "operation": "READ",
        "name": "Agregacja: srednia ocena eventu",
        "description": "GROUP BY event, AVG(rating) z recenzji",
        "json_related": False,
    },
    {
        "id": 11,
        "operation": "READ",
        "name": "Filtr po polu JSON (age_limit)",
        "description": "SELECT eventów gdzie additional_info->age_limit = 18",
        "json_related": True,
    },
    {
        "id": 12,
        "operation": "READ",
        "name": "Top eventy po liczbie bookingow",
        "description": "Ranking wydarzen po liczbie rezerwacji",
        "json_related": False,
    },

    # UPDATE (13-18)
    {
        "id": 13,
        "operation": "UPDATE",
        "name": "Zmień status bookingu",
        "description": "UPDATE bookings SET status='paid' WHERE id=X",
        "json_related": False,
    },
    {
        "id": 14,
        "operation": "UPDATE",
        "name": "Aktualizuj available_quantity",
        "description": "UPDATE tickets SET available_quantity-=1 WHERE id=X",
        "json_related": False,
    },
    {
        "id": 15,
        "operation": "UPDATE",
        "name": "Masowy UPDATE statusu eventów",
        "description": "UPDATE 100 eventów SET status='finished'",
        "json_related": False,
    },
    {
        "id": 16,
        "operation": "UPDATE",
        "name": "Aktualizuj dane użytkownika",
        "description": "UPDATE users SET phone, updated_at WHERE id=X",
        "json_related": False,
    },
    {
        "id": 17,
        "operation": "UPDATE",
        "name": "Aktualizuj pole JSON (languages)",
        "description": "UPDATE additional_info – dodaj język do tablicy languages w evencie",
        "json_related": True,
    },
    {
        "id": 18,
        "operation": "UPDATE",
        "name": "Zmień ceny biletów VIP o 10%",
        "description": "UPDATE tickets SET price=price*1.1 WHERE ticket_type='VIP'",
        "json_related": False,
    },

    # DELETE (19-24)
    {
        "id": 19,
        "operation": "DELETE",
        "name": "Usuń recenzję",
        "description": "DELETE FROM reviews WHERE user_id=X AND event_id=Y",
        "json_related": False,
    },
    {
        "id": 20,
        "operation": "DELETE",
        "name": "Usuń booking (cascade)",
        "description": "DELETE bookingu – cascade usuwa booking_tickets",
        "json_related": False,
    },
    {
        "id": 21,
        "operation": "DELETE",
        "name": "Usuń użytkownika (cascade)",
        "description": "DELETE usera – cascade usuwa bookings, addresses, reviews",
        "json_related": False,
    },
    {
        "id": 22,
        "operation": "DELETE",
        "name": "Usuń eventy cancelled",
        "description": "DELETE eventów ze statusem 'cancelled'",
        "json_related": False,
    },
    {
        "id": 23,
        "operation": "DELETE",
        "name": "Usuń stare płatności",
        "description": "DELETE payments starszych niż 1 rok",
        "json_related": False,
    },
    {
        "id": 24,
        "operation": "DELETE",
        "name": "Usun testowy bilet",
        "description": "DELETE testowego biletu i powiazan",
        "json_related": False,
    },
]
