import pytest
from httpx import AsyncClient, ASGITransport
from src.api import app
from src.security import get_current_user
from src.database import get_db
import random
from sqlalchemy import select
from src import models

# Mock de dependência para ignorar autenticação real nos testes
async def override_get_current_user():
    return models.Usuario(id=1, username="admin", role="trainer")

app.dependency_overrides[get_current_user] = override_get_current_user

@pytest.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

def gerar_cpf_valido() -> str:
    """Gera um CPF válido para testes."""
    def calcula_digito(digs):
        s = 0
        qtd = len(digs)
        peso = qtd + 1
        for i in range(qtd):
            s += digs[i] * peso
            peso -= 1
        r = 11 - (s % 11)
        return 0 if r > 9 else r

    cpf = [random.randint(0, 9) for _ in range(9)]
    cpf.append(calcula_digito(cpf))
    cpf.append(calcula_digito(cpf))
    return "".join(map(str, cpf))

@pytest.mark.anyio
async def test_fluxo_aluno_e_plano(ac: AsyncClient):
    # 1. Criar Aluno
    cpf = gerar_cpf_valido()
    aluno_payload = {
        "nome": "Aluno Teste Sênior",
        "cpf": cpf,
        "valor_mensalidade": 200.0,
        "frequencia_semanal_plano": 3,
        "dia_vencimento": 10
    }
    res_aluno = await ac.post("/alunos/", json=aluno_payload)
    assert res_aluno.status_code == 201
    aluno_id = res_aluno.json()["id"]

    # 2. Criar Exercício Base para a prescrição
    exercicio_payload = {
        "nome": f"Exercício Teste {random.randint(0, 10000)}",
        "grupo_muscular": "Peito"
    }
    res_ex = await ac.post("/exercicios/", json=exercicio_payload)
    ex_id = res_ex.json()["id"] if res_ex.status_code == 201 else 1

    # 3. Criar Plano de Treino (Nova Estrutura)
    plano_payload = {
        "titulo": "Plano A - Hipertrofia",
        "objetivo_estrategico": "Ganho de massa magra",
        "treinos": [
            {
                "nome": "Treino A",
                "prescricoes": [
                    {
                        "exercicio_id": ex_id,
                        "series": 4,
                        "repeticoes": "10",
                        "carga": "60.0",
                        "descanso": 90
                    }
                ]
            }
        ]
    }
    
    res_plano = await ac.post(f"/alunos/{aluno_id}/planos", json=plano_payload)
    
    assert res_plano.status_code == 201
    data = res_plano.json()
    assert data["titulo"] == "Plano A - Hipertrofia"
    assert len(data["treinos"]) == 1
    assert data["treinos"][0]["prescricoes"][0]["nome_exercicio"] is not None

@pytest.mark.anyio
async def test_cpf_duplicado_bloqueio(ac: AsyncClient):
    cpf = gerar_cpf_valido()
    payload = {
        "nome": "Clone",
        "cpf": cpf,
        "valor_mensalidade": 100,
        "frequencia_semanal_plano": 1,
        "dia_vencimento": 1
    }
    # Primeiro cadastro
    await ac.post("/alunos/", json=payload)
    # Segundo cadastro (mesmo CPF)
    response = await ac.post("/alunos/", json=payload)
    
    assert response.status_code == 409
    assert response.json()["type"] == "BusinessRuleViolation"
