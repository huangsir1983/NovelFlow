import { redirect } from 'next/navigation';

interface BoardPageProps {
  params: Promise<{
    locale: string;
    id: string;
  }>;
}

export default async function BoardPage({ params }: BoardPageProps) {
  const { locale, id } = await params;
  redirect(`/${locale}/projects/${id}?stage=canvas`);
}
