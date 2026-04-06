'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { isAdmin } from '@/lib/auth';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    // Chỉ kiểm tra sau khi đã hydrate xong
    if (!isAdmin()) {
      router.replace('/login');
    } else {
      setChecked(true);
    }
  }, [router]);

  // Hiển thị nothing cho đến khi verify xong (tránh flash nội dung)
  if (!checked) return null;

  return <>{children}</>;
}
