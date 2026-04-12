export default function TestLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh" className="dark">
      <body style={{ margin: 0, padding: 0, background: '#000', color: '#fff', fontFamily: 'system-ui, sans-serif' }}>
        {children}
      </body>
    </html>
  );
}
