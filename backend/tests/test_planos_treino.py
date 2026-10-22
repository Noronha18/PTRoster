import pytest
from httpx import AsyncClient, ASGITransport
from src.api import app
from src.security import get_current_user
from src import models
import random

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
async def test_desativacao_automatica_planos(ac: AsyncClient):
    # 1. Criar Aluno
    aluno_payload = {
        "nome": "Aluno Teste Desativação",
        "cpf": gerar_cpf_valido(),
        "valor_mensalidade": 150.0
    }
    res_aluno = await ac.post("/alunos/", json=aluno_payload)
    aluno_id = res_aluno.json()["id"]

    # 2. Criar Primeiro Plano
    plano1_payload = {
        "titulo": "Plano Antigo",
        "duracao_semanas": 4,
        "treinos": []
    }
    res_p1 = await ac.post(f"/alunos/{aluno_id}/planos", json=plano1_payload)
    assert res_p1.json()["esta_ativo"] is True

    # 3. Criar Segundo Plano
    plano2_payload = {
        "titulo": "Plano Novo",
        "duracao_semanas": 8,
        "treinos": []
    }
    res_p2 = await ac.post(f"/alunos/{aluno_id}/planos", json=plano2_payload)
    assert res_p2.json()["esta_ativo"] is True

    # 4. Verificar se o primeiro plano foi desativado
    # Buscamos os dados do aluno para ver todos os planos
    res_aluno_detalhe = await ac.get(f"/alunos/{aluno_id}")
    planos = res_aluno_detalhe.json()["planos_treino"]
    
    plano1 = next(p for p in planos if p["titulo"] == "Plano Antigo")
    plano2 = next(p for p in planos if p["titulo"] == "Plano Novo")
    
    assert plano1["esta_ativo"] is False
    assert plano2["esta_ativo"] is True

@pytest.mark.anyio
async def test_clonagem_de_plano(ac: AsyncClient):
    # 1. Criar Aluno A com um plano e exercícios
    res_ex = await ac.post("/exercicios/", json={"nome": f"Ex Clonagem {random.randint(0,1000)}", "grupo_muscular": "Bíceps"})
    ex_id = res_ex.json()["id"]

    aluno_a_id = (await ac.post("/alunos/", json={"nome": "Aluno A", "cpf": gerar_cpf_valido()})).json()["id"]
    
    plano_origem_payload = {
        "titulo": "Plano Mestre",
        "duracao_semanas": 12,
        "treinos": [
            {
                "nome": "Treino A",
                "prescricoes": [{"exercicio_id": ex_id, "series": 3, "repeticoes": "12", "descanso": 60}]
            }
        ]
    }
    res_origem = await ac.post(f"/alunos/{aluno_a_id}/planos", json=plano_origem_payload)
    plano_origem_id = res_origem.json()["id"]

    # 2. Criar Aluno B
    aluno_b_id = (await ac.post("/alunos/", json={"nome": "Aluno B", "cpf": gerar_cpf_valido()})).json()["id"]

    # 3. Clonar o plano do Aluno A para o Aluno B
    res_clone = await ac.post(f"/planos/{plano_origem_id}/clonar?aluno_id={aluno_b_id}")
    assert res_clone.status_code == 200
    clone_data = res_clone.json()

    assert clone_data["titulo"] == "Plano Mestre (Cópia)"
    assert clone_data["aluno_id"] == aluno_b_id
    assert len(clone_data["treinos"]) == 1
    assert clone_data["treinos"][0]["prescricoes"][0]["exercicio_id"] == ex_id

@pytest.mark.anyio
async def test_edicao_avancada_patch(ac: AsyncClient):
    # 1. Criar setup inicial
    res_ex1 = await ac.post("/exercicios/", json={"nome": f"Ex Patch 1 {random.randint(0,1000)}", "grupo_muscular": "Quadríceps"})
    ex1_id = res_ex1.json()["id"]
    
    aluno_id = (await ac.post("/alunos/", json={"nome": "Aluno Patch", "cpf": gerar_cpf_valido()})).json()["id"]
    
    plano_payload = {
        "titulo": "Plano Original",
        "treinos": [
            {
                "nome": "Treino Original",
                "prescricoes": [{"exercicio_id": ex1_id, "series": 3, "repeticoes": "10", "descanso": 60}]
            }
        ]
    }
    res_init = await ac.post(f"/alunos/{aluno_id}/planos", json=plano_payload)
    plano_data = res_init.json()
    plano_id = plano_data["id"]
    treino_id = plano_data["treinos"][0]["id"]
    prescricao_id = plano_data["treinos"][0]["prescricoes"][0]["id"]

    # 2. Preparar PATCH: 
    # - Mudar título
    # - Atualizar série da prescrição existente
    # - Adicionar novo treino
    # - Remover treino antigo (simulado não enviando ele)
    
    res_ex2 = await ac.post("/exercicios/", json={"nome": f"Ex Patch 2 {random.randint(0,1000)}", "grupo_muscular": "Costas"})
    ex2_id = res_ex2.json()["id"]

    patch_payload = {
        "titulo": "Plano Atualizado",
        "treinos": [
            {
                "id": treino_id,
                "nome": "Treino Editado",
                "prescricoes": [
                    {
                        "id": prescricao_id,
                        "exercicio_id": ex1_id,
                        "series": 5, # Mudou de 3 para 5
                        "repeticoes": "10",
                        "descanso": 60
                    }
                ]
            },
            {
                "nome": "Novo Treino B",
                "prescricoes": [
                    {"exercicio_id": ex2_id, "series": 4, "repeticoes": "12", "descanso": 45}
                ]
            }
        ]
    }

    res_patch = await ac.patch(f"/planos/{plano_id}", json=patch_payload)
    assert res_patch.status_code == 200
    updated_data = res_patch.json()

    assert updated_data["titulo"] == "Plano Atualizado"
    assert len(updated_data["treinos"]) == 2
    
    # Verifica se a prescrição existente foi atualizada
    treino_a = next(t for t in updated_data["treinos"] if t["id"] == treino_id)
    assert treino_a["nome"] == "Treino Editado"
    assert treino_a["prescricoes"][0]["series"] == 5

@pytest.mark.anyio
async def test_criar_template_global(ac: AsyncClient):
    # Criar um plano sem aluno_id (template)
    template_payload = {
        "titulo": "Template Iniciante",
        "duracao_semanas": 4,
        "treinos": []
    }
    res = await ac.post("/planos/templates", json=template_payload)
    assert res.status_code == 201
    data = res.json()
    assert data["aluno_id"] is None
    
    # Listar templates
    res_list = await ac.get("/planos/templates")
    assert res_list.status_code == 200
    templates = res_list.json()
    assert any(t["titulo"] == "Template Iniciante" for t in templates)
