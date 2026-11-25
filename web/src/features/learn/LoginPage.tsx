import { Button, PasswordInput } from '@mantine/core';
import { useState, type FormEvent } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { errorMessage } from '@/api/client';
import { useLogin, useMe } from '@/api/queries';
import { PageHeader } from '@/ui/PageHeader';
import { safeTarget } from './target';
import './learn.css';

export default function LoginPage() {
  const me = useMe().data;
  const login = useLogin();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [password, setPassword] = useState('');
  const target = safeTarget(params.get('to'));
  if (me?.role === 'admin' && !login.isPending) return <Navigate to={target} replace />;

  const submit = (event: FormEvent): void => {
    event.preventDefault();
    login.mutate(password, { onSuccess: () => navigate(target, { replace: true }), onSettled: () => setPassword('') });
  };

  return (
    <>
      <PageHeader title="Вход для авторов" docTitle="Вход" subtitle="Ученикам вход не нужен." />
      <form className="learn-login" onSubmit={submit}>
        <PasswordInput label="Пароль" autoComplete="current-password" required maxLength={500} value={password} onChange={(e) => setPassword(e.currentTarget.value)}
          error={login.isError ? errorMessage(login.error) : null} />
        <Button type="submit" loading={login.isPending}>Войти</Button>
      </form>
    </>
  );
}
