#!/usr/bin/env python3
"""Xóa sạch chunks và gọi reingest"""
import os, sys
sys.stdout.reconfigure(line_buffering=True)

os.environ['SUPABASE_URL'] = 'https://bjvtippltzerfnjvzbgb.supabase.co'
os.environ['SUPABASE_SERVICE_KEY'] = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJqdnRpcHBsdHplcmZuanZ6YmdiIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NTE3OTA1MiwiZXhwIjoyMDkwNzU1MDUyfQ.nIizOga0sCh24F2DUB2WEQqew899dOhN22plOaWvOlU'

from supabase import create_client
sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_KEY'])
book_id = '7583e35a-5972-4030-beed-d1a5644fc469'

# Xóa tất cả chunks cũ bằng batching
while True:
    r = sb.table('book_chunks').select('id').eq('book_id', book_id).limit(50).execute()
    if not r.data:
        break
    ids = [row['id'] for row in r.data]
    sb.table('book_chunks').delete().in_('id', ids).execute()
    print(f'Deleted {len(ids)} chunks', flush=True)

r2 = sb.table('book_chunks').select('id', count='exact').eq('book_id', book_id).execute()
print(f'Remaining: {r2.count} chunks', flush=True)
print('DONE cleaning', flush=True)
