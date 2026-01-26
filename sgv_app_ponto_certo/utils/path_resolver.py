"""
Utilitário para resolver caminhos de arquivos no projeto e executável compilado.
Funciona tanto ao rodar o script quanto no executável gerado pelo PyInstaller.
"""

import os
import shutil
import sys
from pathlib import Path


def get_base_path() -> Path:
    """
    Retorna o caminho base do projeto/aplicação.

    Funciona em 3 cenários:
    1. Desenvolvimento: diretório do script
    2. Executável PyInstaller onefile: pasta temporária _MEIPASS
    3. Executável PyInstaller onedir: diretório do executável

    Returns:
        Path: Caminho base da aplicação
    """

    if getattr(sys, "frozen", False):
        # Executável compilado pelo PyInstaller
        if hasattr(sys, "_MEIPASS"):
            # onefile mode → base para ASSETS embutidos
            return Path(sys._MEIPASS)
        else:
            # onedir mode → executável ao lado de assets
            return Path(sys.executable).parent
    else:
        # Modo desenvolvimento
        return Path(__file__).parent.parent


def get_persistent_base_path() -> Path:
    """
    Retorna o caminho base PERSISTENTE para dados gerados pelo app
    (ex.: banco SQLite, arquivos em data/). Diferente de get_base_path(),
    que aponta para _MEIPASS em onefile (temporário), este sempre aponta
    para uma pasta que persiste entre execuções.

    - onefile: pasta do executável
    - onedir: pasta do executável
    - dev: raiz do projeto
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


def get_asset_path(filename: str) -> str:
    """
    Retorna o caminho absoluto para um arquivo em assets.

    Args:
        filename: Nome do arquivo (ex: "Mercadinho_Ponto_Certo.png")

    Returns:
        Caminho absoluto para o arquivo
    """

    base_path = get_base_path()
    asset_path = base_path / "assets" / filename

    # Debugar se arquivo não for encontrado
    if not asset_path.exists():
        print(f"[WARN] Aviso: Asset não encontrado: {asset_path}")
        print(f"   Base path: {base_path}")
        if (base_path / "assets").exists():
            print(f"   Conteúdo de assets: {list((base_path / 'assets').iterdir())}")
        else:
            print(f"   Pasta assets não existe em {base_path}")

    return str(asset_path)


def get_asset_uri(filename: str) -> str:
    """
    Retorna a URI 'file://...' para uso em componentes UI que aceitam URIs (ex: Flet Image).

    Args:
        filename: nome do asset dentro da pasta assets

    Returns:
        URI string (ex: file:///C:/.../assets/logo.png)
    """

    # Return a URI that works both for Flet Desktop and for the web view.
    # When running with `ft.app(..., assets_dir="assets")`, Flet serves files
    # under the `/assets/` path in the web server. Using that path makes images
    # available in browser mode. Flet Desktop also understands this served
    # path and will load the asset from the configured assets directory.
    try:
        # Flet 0.28.x espera caminho relativo à pasta configurada em assets_dir
        # Ex.: "assets/logo.png" (sem barra inicial)
        return f"assets/{filename}"
    except Exception:
        p = Path(get_asset_path(filename))
        return f"file://{str(p)}"


def get_data_path(filename: str) -> str:
    """
    Retorna o caminho absoluto para um arquivo em data.

    Args:
        filename: Nome do arquivo (ex: "produtos.json")

    Returns:
        Caminho absoluto para o arquivo
    """

    base_path = get_persistent_base_path()
    data_path = base_path / "data" / filename
    return str(data_path)


def get_database_url() -> str:
    """
    Retorna a URL de conexão do banco de dados SQLite.
    Garante que o arquivo seja criado no diretório correto.

    Returns:
        URL do banco de dados (sqlite:///caminho/completo/banco.db)
    """

    # Usar base PERSISTENTE para o banco
    persistent_base = get_persistent_base_path()
    db_path = persistent_base / "mercadinho.db"

    # Criar diretório se não existir
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Se o banco não existir, tentar inicializar a partir de um template embutido
    # Verificar múltiplas localizações possíveis no bundle (ex.: base/mercadinho.db e base/data/mercadinho.db)
    if not db_path.exists():
        try:
            base = Path(get_base_path())
            candidates = [base / "mercadinho.db", base / "data" / "mercadinho.db"]
            for bundled in candidates:
                try:
                    if bundled.exists():
                        shutil.copy2(str(bundled), str(db_path))
                        break
                except Exception:
                    continue
        except Exception:
            pass

    # Retornar URL SQLite com caminho absoluto
    return f"sqlite:///{db_path.absolute()}"
