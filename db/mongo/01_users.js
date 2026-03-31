// ============================================================
// MongoDB – Kolekcja: users
// Plik: db/mongo/01_users.js
// ============================================================
// Uruchamiany automatycznie przez docker-entrypoint-initdb.d
// ============================================================

db = db.getSiblingDB('eventsdb');

db.createCollection('users', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['first_name', 'last_name', 'email', 'password_hash', 'status', 'created_at'],
      properties: {
        first_name: {
          bsonType: 'string',
          description: 'Imię użytkownika – wymagane'
        },
        last_name: {
          bsonType: 'string',
          description: 'Nazwisko użytkownika – wymagane'
        },
        email: {
          bsonType: 'string',
          pattern: '^[a-zA-Z0-9._%+\\-]+@[a-zA-Z0-9.\\-]+\\.[a-zA-Z]{2,}$',
          description: 'Adres e-mail – wymagany, unikalny'
        },
        password_hash: {
          bsonType: 'string',
          description: 'Hash hasła – wymagany'
        },
        phone: {
          bsonType: ['string', 'null'],
          description: 'Numer telefonu – opcjonalny'
        },
        status: {
          bsonType: 'string',
          enum: ['active', 'deleted'],
          description: 'Status konta – active lub deleted'
        },
        // Adresy wbudowane (embedded) – czytane zawsze razem z userem
        addresses: {
          bsonType: ['array', 'null'],
          items: {
            bsonType: 'object',
            required: ['street', 'city', 'postal_code', 'country', 'type'],
            properties: {
              street:      { bsonType: 'string' },
              city:        { bsonType: 'string' },
              postal_code: { bsonType: 'string' },
              country:     { bsonType: 'string' },
              type: {
                bsonType: 'string',
                enum: ['home', 'billing', 'other']
              },
              created_at: { bsonType: 'date' }
            }
          }
        },
        created_at: { bsonType: 'date' },
        updated_at: { bsonType: 'date' }
      }
    }
  },
  validationLevel:  'moderate',
  validationAction: 'warn'
});

// Indeksy
db.users.createIndex({ email: 1 },   { unique: true, name: 'idx_users_email' });
db.users.createIndex({ status: 1 },              { name: 'idx_users_status' });
db.users.createIndex({ 'addresses.city': 1 },    { name: 'idx_users_addr_city' });
db.users.createIndex({ created_at: -1 },         { name: 'idx_users_created_at' });

print('Kolekcja users utworzona z walidacją i indeksami.');