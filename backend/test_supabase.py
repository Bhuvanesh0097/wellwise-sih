from app.supabase_client import supabase


print("\n" + "=" * 60)
print("WELLWISE SUPABASE CONNECTION TEST")
print("=" * 60)

try:
    response = (
        supabase
        .table("wells")
        .select("well_id")
        .limit(5)
        .execute()
    )

    print("\n✅ Supabase connection successful")
    print("Table: wells")
    print("Rows returned:", response.data)

except Exception as error:
    print("\n❌ Supabase connection failed")
    print("Error:", error)

print("\n" + "=" * 60)
