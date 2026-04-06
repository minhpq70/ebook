'use client';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Trash2, Plus, ArrowLeft, Tag } from 'lucide-react';
import { categoriesAPI } from '@/lib/api';

export default function CategoriesPage() {
  const [categories, setCategories] = useState<{ id: string; name: string; sort_order: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState('');
  const [newOrder, setNewOrder] = useState(0);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadCategories();
  }, []);

  const loadCategories = async () => {
    try {
      const data = await categoriesAPI.list();
      setCategories(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName) return;
    setSaving(true);
    try {
      await categoriesAPI.create({ name: newName, sort_order: newOrder });
      setNewName('');
      setNewOrder(0);
      loadCategories();
    } catch (e: any) {
      alert(e.message || 'Lỗi thêm danh mục');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Bạn có chắc chắn muốn xóa danh mục này? Các sách đã gán vẫn giữ được tên danh mục cũ.')) return;
    try {
      await categoriesAPI.delete(id);
      loadCategories();
    } catch (e: any) {
      alert(e.message || 'Lỗi xóa danh mục');
    }
  };

  return (
    <div className="min-h-screen">
      <nav style={{ borderBottom: '1px solid #2d3148', background: 'rgba(15,17,23,0.8)', position: 'sticky', top: 0, zIndex: 50 }}>
        <div style={{ maxWidth: 800, margin: '0 auto', padding: '1rem 1.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Link href="/admin" className="btn-ghost" style={{ padding: '0.5rem 0.75rem' }}>
            <ArrowLeft style={{ width: 16, height: 16 }} />
          </Link>
          <Tag style={{ width: 16, height: 16, color: '#6c63ff' }} />
          <span style={{ fontWeight: 500 }}>Quản lý Danh mục (Categories)</span>
        </div>
      </nav>

      <div style={{ maxWidth: 800, margin: '0 auto', padding: '3rem 1.5rem', display: 'flex', flexDirection: 'column', gap: '2rem' }}>
        {/* Form add */}
        <div className="card" style={{ padding: '2rem' }}>
          <h3 style={{ marginBottom: '1rem', fontWeight: 500 }}>Thêm Danh Mục Mới</h3>
          <form onSubmit={handleAdd} style={{ display: 'grid', gridTemplateColumns: '1fr 100px auto', gap: '1rem', alignItems: 'end' }}>
            <div>
              <label style={{ fontSize: '0.875rem', color: '#8890a4', display: 'block', marginBottom: '0.5rem' }}>Tên danh mục</label>
              <input 
                className="input" placeholder="Ví dụ: Chính trị, Lịch sử..." required
                value={newName} onChange={e => setNewName(e.target.value)} 
              />
            </div>
            <div>
              <label style={{ fontSize: '0.875rem', color: '#8890a4', display: 'block', marginBottom: '0.5rem' }}>Thứ tự hiển thị</label>
              <input 
                className="input" type="number" 
                value={newOrder} onChange={e => setNewOrder(Number(e.target.value))} 
              />
            </div>
            <button type="submit" disabled={saving || !newName} className="btn-primary" style={{ padding: '0.75rem' }}>
              <Plus style={{ width: 16, height: 16 }} /> {saving ? 'Đang thêm...' : 'Thêm'}
            </button>
          </form>
        </div>

        {/* List */}
        <div className="card" style={{ padding: '2rem' }}>
          <h3 style={{ marginBottom: '1.5rem', fontWeight: 500 }}>Danh sách hiện tại</h3>
          {loading ? (
            <p style={{ color: '#8890a4' }}>Đang tải...</p>
          ) : categories.length === 0 ? (
            <p style={{ color: '#8890a4' }}>Chưa có danh mục nào.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {categories.map(cat => (
                <div key={cat.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1rem', background: '#13151f', border: '1px solid #2d3148', borderRadius: '0.75rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <div style={{ width: 32, height: 32, borderRadius: '50%', background: '#2d3148', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.875rem', color: '#8890a4' }}>
                      {cat.sort_order}
                    </div>
                    <span style={{ fontWeight: 500, fontSize: '1rem' }}>{cat.name}</span>
                  </div>
                  <button onClick={() => handleDelete(cat.id)} className="btn-danger" style={{ padding: '0.5rem', background: 'transparent', color: '#ef4444' }}>
                    <Trash2 style={{ width: 16, height: 16 }} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
