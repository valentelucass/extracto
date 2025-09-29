from flask import Flask, render_template, request, jsonify, send_file, make_response
from flask_cors import CORS
import os
import threading
from datetime import datetime, timedelta
import logging
import json
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import time
import re
import tempfile
import io

# Configuração do Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua-chave-secreta-aqui'

# Configuração CORS
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:5000", 
            "http://127.0.0.1:5000", 
            "http://192.168.3.23:5000",
            "https://extracto-lovat.vercel.app"
        ],
        "methods": ["GET", "POST", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Diretório para salvar os resultados (usando temp para Vercel)
RESULTS_DIR = tempfile.mkdtemp() if 'VERCEL' in os.environ else 'resultados'
if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)

# Configurações
# Seletores mais abrangentes para diferentes tipos de conteúdo
SELETORES_CONTEUDO_PRINCIPAL = [
    # Seletores semânticos HTML5
    'main', 'article', 'section',
    
    # Seletores de conteúdo comuns
    '.content', '.main-content', '#content', '.container',
    '.post-content', '.entry-content', '.article-content',
    '.page-content', '.single-content', '.blog-content',
    
    # Seletores específicos de CMS populares
    '.post-body', '.entry-body', '.article-body',
    '.content-area', '.primary-content', '.main-area',
    
    # Seletores de texto e parágrafos
    '.text-content', '.body-text', '.article-text',
    '.story-content', '.news-content',
    
    # Seletores de blogs e notícias
    '.post', '.article', '.story', '.news-item',
    '.blog-post', '.news-article',
    
    # Seletores genéricos mais amplos
    '[role="main"]', '[role="article"]',
    '.wrapper', '.inner', '.site-content'
]

# Seletores expandidos para popups e elementos indesejados
SELETORES_COOKIES_POPUP = [
    '.cookie-banner', '.cookie-notice', '.cookie-consent',
    '#cookie-banner', '#cookie-notice', '.gdpr-banner',
    '.privacy-notice', '.consent-banner', '.cookie-bar',
    '.cookie-popup', '.gdpr-popup', '.privacy-popup',
    '.cookie-overlay', '.consent-overlay', '.privacy-overlay',
    '[data-cookie]', '[data-gdpr]', '[data-consent]'
]

# Novos seletores para elementos que devem ser removidos
SELETORES_ELEMENTOS_INDESEJADOS = [
    # Scripts e estilos
    'script', 'style', 'noscript',
    
    # Navegação e estrutura
    'nav', 'header', 'footer', 'aside',
    '.navigation', '.navbar', '.menu', '.sidebar',
    
    # Publicidade e marketing
    '.advertisement', '.ads', '.ad', '.banner-ad',
    '.google-ads', '.adsense', '.sponsored',
    '.promo', '.promotion', '.marketing',
    
    # Popups e overlays
    '.popup', '.modal', '.overlay', '.lightbox',
    '.dialog', '.tooltip', '.dropdown',
    
    # Social e compartilhamento
    '.social-share', '.share-buttons', '.social-media',
    '.follow-us', '.social-icons',
    
    # Comentários e interação
    '.comments', '.comment-section', '.disqus',
    '.facebook-comments', '.livefyre',
    
    # Elementos de interface
    '.breadcrumb', '.pagination', '.tags',
    '.categories', '.metadata', '.byline',
    
    # Widgets e extras
    '.widget', '.related-posts', '.recommended',
    '.newsletter', '.subscription', '.signup',
    
    # Elementos ocultos
    '[style*="display: none"]', '[style*="visibility: hidden"]',
    '.hidden', '.invisible', '.sr-only'
]

def iniciar_driver():
    """Inicializa o driver do Chrome com configurações otimizadas"""
    logger.info("=== INICIANDO DIAGNÓSTICO DO CHROME WEBDRIVER ===")
    
    chrome_options = Options()
    
    # Configurações básicas para melhor performance
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-plugins')
    chrome_options.add_argument('--disable-images')
    chrome_options.add_argument('--disable-web-security')
    chrome_options.add_argument('--allow-running-insecure-content')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-logging')
    chrome_options.add_argument('--log-level=3')
    chrome_options.add_argument('--silent')
    
    logger.info("Configurações do Chrome definidas")
    
    # Configurações específicas para Vercel (produção)
    if os.environ.get('VERCEL'):
        logger.info("Ambiente VERCEL detectado")
        chrome_options.add_argument('--single-process')
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
        chrome_options.binary_location = '/usr/bin/google-chrome'
    else:
        logger.info("Ambiente LOCAL detectado (Windows)")
        # Para Windows, especificar o caminho do Chrome explicitamente
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        logger.info(f"Definindo caminho do Chrome: {chrome_path}")
        
        # Verificar se o Chrome existe
        if os.path.exists(chrome_path):
            logger.info("Chrome encontrado no caminho especificado")
            chrome_options.binary_location = chrome_path
        else:
            logger.warning(f"Chrome NÃO encontrado em: {chrome_path}")
    
    try:
        # Para ambiente local (Windows)
        if not os.environ.get('VERCEL'):
            logger.info("=== TENTATIVA 1: ChromeDriverManager ===")
            
            try:
                # Primeira tentativa: usar ChromeDriverManager
                logger.info("Importando ChromeDriverManager...")
                from webdriver_manager.chrome import ChromeDriverManager
                
                logger.info("Chamando ChromeDriverManager().install()...")
                driver_path = ChromeDriverManager().install()
                logger.info(f"ChromeDriver instalado em: {driver_path}")
                
                logger.info("Criando Service com o driver path...")
                service = Service(driver_path)
                
                logger.info("Inicializando webdriver.Chrome...")
                driver = webdriver.Chrome(service=service, options=chrome_options)
                
                logger.info("Definindo timeout...")
                driver.set_page_load_timeout(30)
                
                logger.info("✅ Driver Chrome inicializado com SUCESSO usando ChromeDriverManager!")
                return driver
                
            except Exception as e1:
                logger.error(f"❌ ChromeDriverManager FALHOU: {type(e1).__name__}: {e1}")
                import traceback
                logger.error(f"Traceback completo: {traceback.format_exc()}")
                
                logger.info("=== TENTATIVA 2: Sem Service específico ===")
                try:
                    logger.info("Tentando inicializar sem service específico...")
                    driver = webdriver.Chrome(options=chrome_options)
                    driver.set_page_load_timeout(30)
                    logger.info("✅ Driver Chrome inicializado com SUCESSO usando fallback!")
                    return driver
                except Exception as e2:
                    logger.error(f"❌ Fallback FALHOU: {type(e2).__name__}: {e2}")
                    import traceback
                    logger.error(f"Traceback completo: {traceback.format_exc()}")
                    
                    logger.info("=== TENTATIVA 3: Driver path fixo ===")
                    try:
                        # Tentar com o path que sabemos que funciona
                        fixed_driver_path = r"C:\Users\lucas\.wdm\drivers\chromedriver\win64\140.0.7339.207\chromedriver-win32\chromedriver.exe"
                        logger.info(f"Tentando com driver path fixo: {fixed_driver_path}")
                        
                        if os.path.exists(fixed_driver_path):
                            logger.info("Driver path fixo encontrado!")
                            service = Service(fixed_driver_path)
                            driver = webdriver.Chrome(service=service, options=chrome_options)
                            driver.set_page_load_timeout(30)
                            logger.info("✅ Driver Chrome inicializado com SUCESSO usando path fixo!")
                            return driver
                        else:
                            logger.error(f"Driver path fixo NÃO encontrado: {fixed_driver_path}")
                    except Exception as e3:
                        logger.error(f"❌ Path fixo FALHOU: {type(e3).__name__}: {e3}")
                        import traceback
                        logger.error(f"Traceback completo: {traceback.format_exc()}")
                    
                    raise Exception(f"Todas as tentativas falharam. Último erro: {e2}")
        else:
            # Para Vercel, usar chromedriver do sistema
            logger.info("=== CONFIGURAÇÃO VERCEL ===")
            service = Service('/usr/bin/chromedriver')
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(30)
            logger.info("✅ Driver Chrome inicializado com sucesso para Vercel")
            return driver
        
    except Exception as e:
        logger.error(f"❌ ERRO GERAL ao inicializar driver Chrome: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"Traceback completo: {traceback.format_exc()}")
        raise Exception(f"Não foi possível inicializar o Chrome WebDriver: {e}")

def tratar_popups_e_cookies(driver):
    """Remove pop-ups de cookies e consentimento"""
    try:
        wait = WebDriverWait(driver, 3)
        
        # Tenta encontrar e fechar pop-ups de cookies
        for seletor in SELETORES_COOKIES_POPUP:
            try:
                popup = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, seletor)))
                # Procura botão de aceitar/fechar
                botoes = popup.find_elements(By.CSS_SELECTOR, 
                    'button, .accept, .close, [onclick], a')
                for botao in botoes:
                    texto = botao.text.lower()
                    if any(palavra in texto for palavra in ['accept', 'aceitar', 'ok', 'fechar', 'close']):
                        botao.click()
                        time.sleep(1)
                        break
                break
            except:
                continue
    except:
        pass

def rolar_pagina_inteligente(driver):
    """Rola a página para carregar conteúdo dinâmico"""
    try:
        altura_anterior = 0
        tentativas = 0
        max_tentativas = 5
        
        while tentativas < max_tentativas:
            # Rola até o final da página
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Verifica se a altura mudou
            nova_altura = driver.execute_script("return document.body.scrollHeight")
            if nova_altura == altura_anterior:
                break
                
            altura_anterior = nova_altura
            tentativas += 1
            
        # Volta ao topo
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        
    except Exception as e:
        logger.warning(f"Erro no scroll inteligente: {e}")

def extrair_com_requests(url):
    """Extrai conteúdo usando requests + BeautifulSoup (para Vercel) - VERSÃO ROBUSTA"""
    import time
    import random
    
    try:
        logger.info("=== USANDO MÉTODO REQUESTS + BEAUTIFULSOUP ROBUSTO ===")
        
        # Múltiplos User-Agents para evitar bloqueios
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0'
        ]
        
        # Configurações de timeout progressivas
        timeout_configs = [
            (5, 10),   # (connect_timeout, read_timeout)
            (10, 15),
            (15, 25),
            (20, 30)
        ]
        
        logger.info(f"Fazendo requisição para: {url}")
        
        # Sistema de retry com backoff exponencial
        max_retries = 4
        base_delay = 1
        
        for attempt in range(max_retries):
            try:
                # Selecionar User-Agent aleatório
                selected_ua = random.choice(user_agents)
                connect_timeout, read_timeout = timeout_configs[min(attempt, len(timeout_configs)-1)]
                
                headers = {
                    'User-Agent': selected_ua,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8,es;q=0.7',
                    'Accept-Encoding': 'identity',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Cache-Control': 'no-cache',
                    'DNT': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none'
                }
                
                logger.info(f"Tentativa {attempt + 1}/{max_retries} - Timeout: {connect_timeout}s/{read_timeout}s")
                
                # Configurar sessão com retry adapter
                session = requests.Session()
                session.headers.update(headers)
                
                # Fazer requisição com timeout específico
                response = session.get(
                    url, 
                    timeout=(connect_timeout, read_timeout),
                    allow_redirects=True,
                    verify=True
                )
                response.raise_for_status()
                
                logger.info(f"✅ Sucesso na tentativa {attempt + 1}")
                break
                
            except (requests.exceptions.ConnectTimeout, 
                    requests.exceptions.ReadTimeout,
                    requests.exceptions.Timeout) as e:
                logger.warning(f"⏱️ Timeout na tentativa {attempt + 1}: {e}")
                
                if attempt < max_retries - 1:
                    # Backoff exponencial com jitter
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.info(f"🔄 Aguardando {delay:.1f}s antes da próxima tentativa...")
                    time.sleep(delay)
                else:
                    logger.error("❌ Todas as tentativas de conexão falharam")
                    raise
                    
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"🔌 Erro de conexão na tentativa {attempt + 1}: {e}")
                
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 2)
                    logger.info(f"🔄 Aguardando {delay:.1f}s antes da próxima tentativa...")
                    time.sleep(delay)
                else:
                    raise
                    
            except Exception as e:
                logger.error(f"❌ Erro inesperado na tentativa {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    raise
        
        logger.info(f"Resposta recebida: {response.status_code}")
        logger.info(f"Content-Type: {response.headers.get('content-type', 'N/A')}")
        logger.info(f"Content-Length: {len(response.content)} bytes")
        logger.info(f"Encoding detectado: {response.encoding}")
        
        # Tentar diferentes encodings se necessário
        html_content = None
        encodings_to_try = [response.encoding, 'utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
        
        for encoding in encodings_to_try:
            if encoding:
                try:
                    html_content = response.content.decode(encoding)
                    logger.info(f"Sucesso com encoding: {encoding}")
                    break
                except (UnicodeDecodeError, LookupError):
                    logger.warning(f"Falha com encoding: {encoding}")
                    continue
        
        if not html_content:
            # Fallback: usar response.text que faz detecção automática
            html_content = response.text
            logger.info("Usando response.text como fallback")
        
        # Tentar diferentes parsers
        soup = None
        parsers = ['html.parser', 'lxml', 'html5lib']
        
        for parser in parsers:
            try:
                soup = BeautifulSoup(html_content, parser)
                logger.info(f"Parser usado com sucesso: {parser}")
                break
            except Exception as e:
                logger.warning(f"Parser {parser} falhou: {e}")
                continue
        
        if not soup:
            # Fallback final
            soup = BeautifulSoup(html_content, 'html.parser')
            logger.info("Usando html.parser como fallback final")
        
        # Extrai título
        titulo = ""
        if soup.title:
            titulo = soup.title.get_text().strip()
        
        # Extrai metadados
        metadados = {}
        try:
            desc_meta = soup.find('meta', attrs={'name': 'description'})
            if desc_meta:
                metadados['description'] = desc_meta.get('content', '')
        except:
            pass
        
        try:
            keywords_meta = soup.find('meta', attrs={'name': 'keywords'})
            if keywords_meta:
                metadados['keywords'] = keywords_meta.get('content', '')
        except:
            pass
        
        try:
            author_meta = soup.find('meta', attrs={'name': 'author'})
            if author_meta:
                metadados['author'] = author_meta.get('content', '')
        except:
            pass
        
        # Remove apenas elementos críticos indesejados (mais seletivo)
        elementos_criticos = ['script', 'style', 'noscript']
        for tag in elementos_criticos:
            for elemento in soup.find_all(tag):
                elemento.decompose()
        
        # Remove elementos de publicidade e navegação
        seletores_ads = ['.advertisement', '.ads', '.ad', '.banner-ad', '.google-ads', 
                        '.adsense', '.sponsored', '.promo', '.promotion']
        for seletor in seletores_ads:
            for elemento in soup.select(seletor):
                elemento.decompose()
        
        # Coletar TODOS os conteúdos possíveis (estratégia múltipla)
        conteudos_extraidos = []
        
        # Estratégia 1: Seletores de conteúdo principal
        logger.info("Extraindo por seletores principais...")
        for seletor in SELETORES_CONTEUDO_PRINCIPAL:
            try:
                elementos = soup.select(seletor)
                for elemento in elementos:
                    texto = elemento.get_text(separator=' ', strip=True)
                    if len(texto) > 20:  # Reduzido para capturar mais conteúdo
                        conteudos_extraidos.append(('seletor_principal', texto))
            except:
                continue
        
        # Estratégia 2: TODOS os parágrafos
        logger.info("Extraindo parágrafos...")
        paragrafos = soup.find_all('p')
        for p in paragrafos:
            texto_p = p.get_text(strip=True)
            if len(texto_p) > 10:  # Mais inclusivo
                conteudos_extraidos.append(('paragrafo', texto_p))
        
        # Estratégia 3: TODAS as divs com texto significativo
        logger.info("Extraindo divs...")
        divs = soup.find_all('div')
        for div in divs:
            texto_div = div.get_text(strip=True)
            if len(texto_div) > 15 and len(texto_div) < 2000:  # Evita divs muito grandes
                # Verifica se não é só texto de elementos filhos já capturados
                texto_direto = div.get_text(strip=True)
                if texto_direto:
                    conteudos_extraidos.append(('div_conteudo', texto_div))
        
        # Estratégia 4: Headers (h1, h2, h3, etc.)
        logger.info("Extraindo headers...")
        for i in range(1, 7):
            headers = soup.find_all(f'h{i}')
            for header in headers:
                texto_header = header.get_text(strip=True)
                if len(texto_header) > 3:
                    conteudos_extraidos.append(('header', texto_header))
        
        # Estratégia 5: Spans com texto
        logger.info("Extraindo spans...")
        spans = soup.find_all('span')
        for span in spans:
            texto_span = span.get_text(strip=True)
            if len(texto_span) > 10:
                conteudos_extraidos.append(('span', texto_span))
        
        # Estratégia 6: Links com texto significativo
        logger.info("Extraindo links...")
        links = soup.find_all('a')
        for link in links:
            texto_link = link.get_text(strip=True)
            if len(texto_link) > 5:
                conteudos_extraidos.append(('link', texto_link))
        
        # Estratégia 7: Listas (ul, ol)
        logger.info("Extraindo listas...")
        listas = soup.find_all(['ul', 'ol'])
        for lista in listas:
            texto_lista = lista.get_text(separator=' ', strip=True)
            if len(texto_lista) > 10:
                conteudos_extraidos.append(('lista', texto_lista))
        
        # Estratégia 8: Tabelas
        logger.info("Extraindo tabelas...")
        tabelas = soup.find_all('table')
        for tabela in tabelas:
            texto_tabela = tabela.get_text(separator=' | ', strip=True)
            if len(texto_tabela) > 10:
                conteudos_extraidos.append(('tabela', texto_tabela))
        
        # Estratégia 9: Fallback para body completo se pouco conteúdo
        if len(conteudos_extraidos) < 5:
            logger.info("Poucos elementos encontrados, usando fallback do body...")
            body = soup.find('body')
            if body:
                texto_body = body.get_text(separator=' ', strip=True)
                conteudos_extraidos.append(('body_completo', texto_body))
        
        # Combinar TODOS os conteúdos únicos
        logger.info(f"Total de elementos extraídos: {len(conteudos_extraidos)}")
        textos_unicos = set()
        conteudo_final_partes = []
        
        # Priorizar por tipo e adicionar conteúdos únicos
        tipos_priorizados = ['header', 'seletor_principal', 'paragrafo', 'div_conteudo', 
                           'lista', 'tabela', 'span', 'link', 'body_completo']
        
        for tipo in tipos_priorizados:
            for tipo_atual, texto in conteudos_extraidos:
                if tipo_atual == tipo and texto not in textos_unicos and len(texto.strip()) > 3:
                    # Evita duplicatas muito similares
                    texto_normalizado = re.sub(r'\s+', ' ', texto.strip().lower())
                    if not any(texto_normalizado in existing.lower() or existing.lower() in texto_normalizado 
                             for existing in textos_unicos if len(existing) > 50):
                        textos_unicos.add(texto)
                        conteudo_final_partes.append(texto)
        
        melhor_conteudo = '\n\n'.join(conteudo_final_partes)
        
        # Limpar e processar o texto final
        if melhor_conteudo:
            # Remover linhas vazias excessivas
            linhas = melhor_conteudo.split('\n')
            linhas_limpas = []
            linha_vazia_anterior = False
            
            for linha in linhas:
                linha = linha.strip()
                if linha:
                    # Filtrar linhas muito curtas que podem ser ruído
                    if len(linha) > 3:
                        # Remove múltiplos espaços
                        linha = re.sub(r'\s+', ' ', linha)
                        linhas_limpas.append(linha)
                    linha_vazia_anterior = False
                elif not linha_vazia_anterior and linhas_limpas:
                    linhas_limpas.append('')
                    linha_vazia_anterior = True
            
            # Remover linhas duplicadas consecutivas
            linhas_finais = []
            linha_anterior = ""
            for linha in linhas_limpas:
                if linha != linha_anterior:
                    linhas_finais.append(linha)
                linha_anterior = linha
            
            melhor_conteudo = '\n'.join(linhas_finais)
        
        # Montar conteúdo final com metadados
        conteudo_final = f"=== EXTRAÇÃO AVANÇADA DE TEXTO by @valentelucass ===\n"
        conteudo_final += f"TÍTULO: {titulo}\n"
        conteudo_final += f"URL: {url}\n"
        conteudo_final += f"DATA: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        conteudo_final += f"MÉTODO: Requests + BeautifulSoup (Vercel)\n"
        
        if metadados.get('description'):
            conteudo_final += f"DESCRIÇÃO: {metadados['description']}\n"
        if metadados.get('author'):
            conteudo_final += f"AUTOR: {metadados['author']}\n"
        if metadados.get('keywords'):
            conteudo_final += f"PALAVRAS-CHAVE: {metadados['keywords']}\n"
        
        conteudo_final += "=" * 60 + "\n\n"
        conteudo_final += melhor_conteudo if melhor_conteudo else "Nenhum conteúdo significativo encontrado."
        
        logger.info(f"Conteúdo extraído com sucesso: {len(conteudo_final)} caracteres")
        return conteudo_final
        
    except Exception as e:
        logger.error(f"Erro na extração com requests: {e}")
        raise

def processar_url(url, nome_arquivo=None):
    """Processa uma URL e salva o resultado em arquivo .txt"""
    try:
        logger.info(f"Iniciando extração de: {url}")
        
        # Gera nome do arquivo se não fornecido
        if not nome_arquivo:
            # Extrai domínio da URL para criar um nome mais descritivo
            try:
                from urllib.parse import urlparse
                parsed_url = urlparse(url)
                domain = parsed_url.netloc.replace('www.', '').replace('.', '_')
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                nome_arquivo = f"{domain}_{timestamp}.txt"
            except:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                nome_arquivo = f"extracao_{timestamp}.txt"
        
        # Garante que o arquivo tenha extensão .txt
        if not nome_arquivo.endswith('.txt'):
            nome_arquivo += '.txt'
        
        caminho_arquivo = os.path.join(RESULTS_DIR, nome_arquivo)
        
        # Escolhe o método de extração baseado no ambiente
        if os.environ.get('VERCEL'):
            logger.info("=== AMBIENTE VERCEL: Usando requests + BeautifulSoup ===")
            conteudo = extrair_com_requests(url)
        else:
            logger.info("=== AMBIENTE LOCAL: Usando Selenium ===")
            # Inicia o driver e faz a extração
            driver = iniciar_driver()
            
            try:
                driver.get(url)
                logger.info("Página carregada, aguardando...")
                time.sleep(3)
                
                # Trata pop-ups e cookies
                tratar_popups_e_cookies(driver)
                
                # Rola a página inteligentemente
                rolar_pagina_inteligente(driver)
                
                # Extrai o conteúdo usando método avançado
                conteudo = extrair_conteudo_avancado(driver, url)
                
            finally:
                driver.quit()
        
        # Salva no arquivo .txt
        with open(caminho_arquivo, 'w', encoding='utf-8') as f:
            f.write(conteudo)
        
        logger.info(f"Extração concluída: {caminho_arquivo}")
        
        return {
            'sucesso': True,
            'arquivo': nome_arquivo,
            'caminho': caminho_arquivo,
            'tamanho': len(conteudo),
            'mensagem': 'Extração concluída com sucesso!'
        }
            
    except Exception as e:
        logger.error(f"Erro na extração: {e}")
        return {
            'sucesso': False,
            'erro': str(e),
            'mensagem': f'Erro durante a extração: {str(e)}'
        }

def extrair_conteudo_avancado(driver, url):
    """Extrai conteúdo de forma avançada e abrangente - VERSÃO MELHORADA"""
    try:
        logger.info("=== INICIANDO EXTRAÇÃO AVANÇADA COM SELENIUM ===")
        
        # Aguardar carregamento completo
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # Obter título da página
        titulo = driver.title.strip()
        logger.info(f"Título extraído: {titulo}")
        
        # Aguardar elementos dinâmicos carregarem
        time.sleep(3)
        
        # Executar scroll inteligente para carregar conteúdo lazy-loaded
        logger.info("Executando scroll inteligente...")
        driver.execute_script("""
            let totalHeight = 0;
            let distance = 100;
            let timer = setInterval(() => {
                let scrollHeight = document.body.scrollHeight;
                window.scrollBy(0, distance);
                totalHeight += distance;
                if(totalHeight >= scrollHeight){
                    clearInterval(timer);
                    window.scrollTo(0, 0); // Volta ao topo
                }
            }, 100);
        """)
        time.sleep(5)
        
        # Aguardar mais um pouco para garantir que tudo carregou
        time.sleep(2)
        
        # Remover apenas elementos críticos indesejados (mais seletivo)
        logger.info("Removendo elementos indesejados...")
        elementos_criticos = ['script', 'style', 'noscript']
        for seletor in elementos_criticos:
            try:
                elementos = driver.find_elements(By.CSS_SELECTOR, seletor)
                for elemento in elementos:
                    driver.execute_script("arguments[0].remove();", elemento)
            except:
                continue
        
        # Remove elementos de publicidade
        seletores_ads = ['.advertisement', '.ads', '.ad', '.banner-ad', '.google-ads', 
                        '.adsense', '.sponsored', '.promo', '.promotion']
        for seletor in seletores_ads:
            try:
                elementos = driver.find_elements(By.CSS_SELECTOR, seletor)
                for elemento in elementos:
                    driver.execute_script("arguments[0].remove();", elemento)
            except:
                continue
        
        # Coletar TODOS os conteúdos possíveis (estratégia múltipla)
        conteudos_extraidos = []
        
        # Estratégia 1: Seletores de conteúdo principal
        logger.info("Extraindo por seletores principais...")
        for seletor in SELETORES_CONTEUDO_PRINCIPAL:
            try:
                elementos = driver.find_elements(By.CSS_SELECTOR, seletor)
                for elemento in elementos:
                    texto = elemento.text.strip()
                    if len(texto) > 20:  # Reduzido para capturar mais conteúdo
                        conteudos_extraidos.append(('seletor_principal', texto))
            except:
                continue
        
        # Estratégia 2: TODOS os parágrafos
        logger.info("Extraindo parágrafos...")
        try:
            paragrafos = driver.find_elements(By.TAG_NAME, 'p')
            for p in paragrafos:
                texto_p = p.text.strip()
                if len(texto_p) > 10:  # Mais inclusivo
                    conteudos_extraidos.append(('paragrafo', texto_p))
        except:
            pass
        
        # Estratégia 3: TODAS as divs com texto significativo
        logger.info("Extraindo divs...")
        try:
            divs = driver.find_elements(By.TAG_NAME, 'div')
            for div in divs:
                texto_div = div.text.strip()
                if len(texto_div) > 15 and len(texto_div) < 3000:  # Mais flexível
                    conteudos_extraidos.append(('div_conteudo', texto_div))
        except:
            pass
        
        # Estratégia 4: Spans com texto
        logger.info("Extraindo spans...")
        try:
            spans = driver.find_elements(By.TAG_NAME, 'span')
            for span in spans:
                texto_span = span.text.strip()
                if len(texto_span) > 10:
                    conteudos_extraidos.append(('span', texto_span))
        except:
            pass
        
        # Estratégia 5: Headers (h1, h2, h3, etc.)
        logger.info("Extraindo headers...")
        try:
            for i in range(1, 7):
                headers = driver.find_elements(By.TAG_NAME, f'h{i}')
                for header in headers:
                    texto_header = header.text.strip()
                    if len(texto_header) > 3:
                        conteudos_extraidos.append(('header', texto_header))
        except:
            pass
        
        # Estratégia 6: Links com texto significativo
        logger.info("Extraindo links...")
        try:
            links = driver.find_elements(By.TAG_NAME, 'a')
            for link in links:
                texto_link = link.text.strip()
                if len(texto_link) > 5:
                    conteudos_extraidos.append(('link', texto_link))
        except:
            pass
        
        # Estratégia 7: Listas (ul, ol)
        logger.info("Extraindo listas...")
        try:
            listas = driver.find_elements(By.CSS_SELECTOR, 'ul, ol')
            for lista in listas:
                texto_lista = lista.text.strip()
                if len(texto_lista) > 10:
                    conteudos_extraidos.append(('lista', texto_lista))
        except:
            pass
        
        # Estratégia 8: Tabelas
        logger.info("Extraindo tabelas...")
        try:
            tabelas = driver.find_elements(By.TAG_NAME, 'table')
            for tabela in tabelas:
                texto_tabela = tabela.text.strip()
                if len(texto_tabela) > 10:
                    conteudos_extraidos.append(('tabela', texto_tabela))
        except:
            pass
        
        # Estratégia 9: Elementos com texto visível (mais abrangente)
        logger.info("Extraindo elementos com texto visível...")
        try:
            # Busca por qualquer elemento que tenha texto e seja visível
            elementos_com_texto = driver.execute_script("""
                var elementos = [];
                var todosElementos = document.querySelectorAll('*');
                for (var i = 0; i < todosElementos.length; i++) {
                    var el = todosElementos[i];
                    if (el.innerText && el.innerText.trim().length > 10 && 
                        el.offsetParent !== null && 
                        getComputedStyle(el).display !== 'none' &&
                        getComputedStyle(el).visibility !== 'hidden') {
                        elementos.push(el.innerText.trim());
                    }
                }
                return elementos;
            """)
            
            for texto in elementos_com_texto:
                if len(texto) > 15 and len(texto) < 2000:
                    conteudos_extraidos.append(('elemento_visivel', texto))
        except:
            pass
        
        # Estratégia 10: Fallback para body completo se pouco conteúdo
        if len(conteudos_extraidos) < 10:
            logger.info("Poucos elementos encontrados, usando fallback do body...")
            try:
                body = driver.find_element(By.TAG_NAME, 'body')
                texto_body = body.text.strip()
                conteudos_extraidos.append(('body_completo', texto_body))
            except:
                pass
        
        # Combinar TODOS os conteúdos únicos
        logger.info(f"Total de elementos extraídos: {len(conteudos_extraidos)}")
        textos_unicos = set()
        conteudo_final_partes = []
        
        # Priorizar por tipo e adicionar conteúdos únicos
        tipos_priorizados = ['header', 'seletor_principal', 'paragrafo', 'div_conteudo', 
                           'lista', 'tabela', 'span', 'link', 'elemento_visivel', 'body_completo']
        
        for tipo in tipos_priorizados:
            for tipo_atual, texto in conteudos_extraidos:
                if tipo_atual == tipo and texto not in textos_unicos and len(texto.strip()) > 3:
                    # Evita duplicatas muito similares
                    texto_normalizado = re.sub(r'\s+', ' ', texto.strip().lower())
                    if not any(texto_normalizado in existing.lower() or existing.lower() in texto_normalizado 
                             for existing in textos_unicos if len(existing) > 50):
                        textos_unicos.add(texto)
                        conteudo_final_partes.append(texto)
        
        melhor_conteudo = '\n\n'.join(conteudo_final_partes)
        
        # Limpar e processar o texto final
        if melhor_conteudo:
            # Remover linhas vazias excessivas
            linhas = melhor_conteudo.split('\n')
            linhas_limpas = []
            linha_vazia_anterior = False
            
            for linha in linhas:
                linha = linha.strip()
                if linha:
                    # Filtrar linhas muito curtas que podem ser ruído
                    if len(linha) > 3:
                        # Remove múltiplos espaços
                        linha = re.sub(r'\s+', ' ', linha)
                        linhas_limpas.append(linha)
                    linha_vazia_anterior = False
                elif not linha_vazia_anterior and linhas_limpas:
                    linhas_limpas.append('')
                    linha_vazia_anterior = True
            
            # Remover linhas duplicadas consecutivas
            linhas_finais = []
            linha_anterior = ""
            for linha in linhas_limpas:
                if linha != linha_anterior:
                    linhas_finais.append(linha)
                linha_anterior = linha
            
            melhor_conteudo = '\n'.join(linhas_finais)
        
        # Extrair metadados adicionais
        metadados = extrair_metadados(driver)
        
        # Montar conteúdo final
        conteudo_final = f"=== EXTRAÇÃO AVANÇADA DE TEXTO by @valentelucass ===\n"
        conteudo_final += f"TÍTULO: {titulo}\n"
        conteudo_final += f"URL: {url}\n"
        conteudo_final += f"DATA: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        conteudo_final += f"MÉTODO: Selenium WebDriver (Local)\n"
        
        if metadados:
            if metadados.get('description'):
                conteudo_final += f"DESCRIÇÃO: {metadados['description']}\n"
            if metadados.get('author'):
                conteudo_final += f"AUTOR: {metadados['author']}\n"
            if metadados.get('keywords'):
                conteudo_final += f"PALAVRAS-CHAVE: {metadados['keywords']}\n"
        
        conteudo_final += "=" * 60 + "\n\n"
        conteudo_final += melhor_conteudo if melhor_conteudo else "Nenhum conteúdo significativo encontrado."
        
        logger.info(f"Extração concluída: {len(conteudo_final)} caracteres")
        return conteudo_final
        
    except Exception as e:
        logger.error(f"Erro na extração avançada: {e}")
        # Fallback para extração simples
        try:
            return extrair_conteudo_simples(driver, url)
        except:
            return f"Erro na extração: {str(e)}"
        try:
            divs = driver.find_elements(By.TAG_NAME, 'div')
            for div in divs:
                texto_div = div.text.strip()
                if len(texto_div) > 15 and len(texto_div) < 2000:  # Mais flexível
                    conteudos_extraidos.append(('div_conteudo', texto_div))
        except:
            pass
        
        # Estratégia 4: Spans com texto
        try:
            spans = driver.find_elements(By.TAG_NAME, 'span')
            for span in spans:
                texto_span = span.text.strip()
                if len(texto_span) > 10:
                    conteudos_extraidos.append(('span', texto_span))
        except:
            pass
        
        # Estratégia 5: Headers (h1, h2, h3, etc.)
        try:
            for i in range(1, 7):
                headers = driver.find_elements(By.TAG_NAME, f'h{i}')
                for header in headers:
                    texto_header = header.text.strip()
                    if len(texto_header) > 3:
                        conteudos_extraidos.append(('header', texto_header))
        except:
            pass
        
        # Estratégia 6: Links com texto significativo
        try:
            links = driver.find_elements(By.TAG_NAME, 'a')
            for link in links:
                texto_link = link.text.strip()
                if len(texto_link) > 5:
                    conteudos_extraidos.append(('link', texto_link))
        except:
            pass
        
        # Estratégia 7: Listas (ul, ol)
        try:
            listas = driver.find_elements(By.CSS_SELECTOR, 'ul, ol')
            for lista in listas:
                texto_lista = lista.text.strip()
                if len(texto_lista) > 10:
                    conteudos_extraidos.append(('lista', texto_lista))
        except:
            pass
        
        # Estratégia 8: Fallback para body completo
        if not conteudos_extraidos:
            try:
                body = driver.find_element(By.TAG_NAME, 'body')
                texto_body = body.text.strip()
                conteudos_extraidos.append(('body_completo', texto_body))
            except:
                pass
        
        # Combinar TODOS os conteúdos únicos
        textos_unicos = set()
        conteudo_final_partes = []
        
        # Priorizar por tipo e adicionar conteúdos únicos
        tipos_priorizados = ['header', 'seletor_principal', 'paragrafo', 'div_conteudo', 'lista', 'span', 'link', 'body_completo']
        
        for tipo in tipos_priorizados:
            for tipo_atual, texto in conteudos_extraidos:
                if tipo_atual == tipo and texto not in textos_unicos and len(texto.strip()) > 3:
                    textos_unicos.add(texto)
                    conteudo_final_partes.append(texto)
        
        melhor_conteudo = '\n\n'.join(conteudo_final_partes)
        
        # Limpar e processar o texto
        if melhor_conteudo:
            # Remover linhas vazias excessivas
            linhas = melhor_conteudo.split('\n')
            linhas_limpas = []
            linha_vazia_anterior = False
            
            for linha in linhas:
                linha = linha.strip()
                if linha:
                    # Filtrar linhas muito curtas que podem ser ruído
                    if len(linha) > 3:
                        linhas_limpas.append(linha)
                    linha_vazia_anterior = False
                elif not linha_vazia_anterior and linhas_limpas:
                    linhas_limpas.append('')
                    linha_vazia_anterior = True
            
            # Remover linhas duplicadas consecutivas
            linhas_finais = []
            linha_anterior = ""
            for linha in linhas_limpas:
                if linha != linha_anterior:
                    linhas_finais.append(linha)
                linha_anterior = linha
            
            melhor_conteudo = '\n'.join(linhas_finais)
        
        # Extrair metadados adicionais
        metadados = extrair_metadados(driver)
        
        # Montar conteúdo final
        conteudo_final = f"=== EXTRAÇÃO AVANÇADA DE TEXTO by @valentelucass ===\n"
        conteudo_final += f"TÍTULO: {titulo}\n"
        conteudo_final += f"URL: {url}\n"
        conteudo_final += f"DATA: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        
        if metadados:
            conteudo_final += f"DESCRIÇÃO: {metadados.get('description', 'N/A')}\n"
            conteudo_final += f"AUTOR: {metadados.get('author', 'N/A')}\n"
            conteudo_final += f"PALAVRAS-CHAVE: {metadados.get('keywords', 'N/A')}\n"
        
        conteudo_final += "=" * 60 + "\n\n"
        conteudo_final += melhor_conteudo if melhor_conteudo else "Nenhum conteúdo significativo encontrado."
        
        return conteudo_final
        
    except Exception as e:
        logger.error(f"Erro na extração avançada: {e}")
        # Fallback para extração simples
        return extrair_conteudo_simples(driver, url)

def extrair_metadados(driver):
    """Extrai metadados da página"""
    metadados = {}
    
    try:
        # Meta description
        try:
            desc_element = driver.find_element(By.CSS_SELECTOR, 'meta[name="description"]')
            metadados['description'] = desc_element.get_attribute('content')
        except:
            pass
        
        # Meta keywords
        try:
            keywords_element = driver.find_element(By.CSS_SELECTOR, 'meta[name="keywords"]')
            metadados['keywords'] = keywords_element.get_attribute('content')
        except:
            pass
        
        # Author
        try:
            author_element = driver.find_element(By.CSS_SELECTOR, 'meta[name="author"]')
            metadados['author'] = author_element.get_attribute('content')
        except:
            # Tentar outras formas de encontrar autor
            try:
                author_selectors = ['.author', '.by-author', '.post-author', '[rel="author"]']
                for selector in author_selectors:
                    author_elem = driver.find_element(By.CSS_SELECTOR, selector)
                    metadados['author'] = author_elem.text.strip()
                    break
            except:
                pass
    
    except Exception as e:
        logger.error(f"Erro ao extrair metadados: {e}")
    
    return metadados

def extrair_conteudo_simples(driver, url):
    """Extrai conteúdo de forma simples para arquivo .txt"""
    try:
        # Obter título da página
        titulo = driver.title.strip()
        
        # Tentar encontrar o conteúdo principal
        conteudo_principal = None
        for seletor in SELETORES_CONTEUDO_PRINCIPAL:
            try:
                elemento = driver.find_element(By.CSS_SELECTOR, seletor)
                conteudo_principal = elemento
                break
            except:
                continue
        
        # Se não encontrou conteúdo principal, usar body
        if not conteudo_principal:
            conteudo_principal = driver.find_element(By.TAG_NAME, 'body')
        
        # Remover elementos indesejados
        elementos_remover = [
            'script', 'style', 'nav', 'header', 'footer',
            'aside', '.advertisement', '.ads', '.popup',
            '.cookie-banner', '.social-share', '.comments'
        ]
        
        for seletor in elementos_remover:
            try:
                elementos = driver.find_elements(By.CSS_SELECTOR, seletor)
                for elemento in elementos:
                    driver.execute_script("arguments[0].remove();", elemento)
            except:
                continue
        
        # Extrair texto limpo
        texto_limpo = conteudo_principal.text.strip()
        
        # Limpar texto (remover linhas vazias excessivas)
        linhas = texto_limpo.split('\n')
        linhas_limpas = []
        linha_vazia_anterior = False
        
        for linha in linhas:
            linha = linha.strip()
            if linha:
                linhas_limpas.append(linha)
                linha_vazia_anterior = False
            elif not linha_vazia_anterior:
                linhas_limpas.append('')
                linha_vazia_anterior = True
        
        # Montar conteúdo final
        conteudo_final = f"=== EXTRAÇÃO DE TEXTO ===\n"
        conteudo_final += f"TÍTULO: {titulo}\n"
        conteudo_final += f"URL: {url}\n"
        conteudo_final += f"DATA: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        conteudo_final += "=" * 50 + "\n\n"
        conteudo_final += '\n'.join(linhas_limpas)
        
        return conteudo_final
        
    except Exception as e:
        return f"Erro ao extrair conteúdo: {str(e)}"

@app.route('/')
def index():
    """Servir a página principal do front-end"""
    return send_file('front-end/index.html')

# Rotas para servir arquivos estáticos do front-end
@app.route('/styles.css')
def serve_css():
    """Servir arquivo CSS"""
    return send_file('front-end/styles.css')

@app.route('/script.js')
def serve_js():
    """Servir arquivo JavaScript"""
    return send_file('front-end/script.js')

@app.route('/favicon.ico')
def serve_favicon():
    """Servir favicon"""
    return send_file('front-end/favicon.ico')

@app.route('/front-end/<path:filename>')
def serve_frontend_static(filename):
    """Servir outros arquivos estáticos do front-end"""
    return send_file(f'front-end/{filename}')

@app.route('/extrair', methods=['POST'])
def extrair():
    """Endpoint para extrair conteúdo de uma URL"""
    try:
        data = request.get_json()
        url = data.get('url')
        filename = data.get('filename')
        
        if not url:
            return jsonify({'sucesso': False, 'mensagem': 'URL é obrigatória'})
        
        # Validar URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        resultado = processar_url(url, filename)
        return jsonify(resultado)
        
    except Exception as e:
        logger.error(f"Erro no endpoint /extrair: {e}")
        return jsonify({
            'sucesso': False,
            'mensagem': f'Erro interno: {str(e)}'
        })

@app.route('/arquivos')
def listar_arquivos():
    """Lista todos os arquivos extraídos"""
    try:
        arquivos = []
        
        if os.path.exists(RESULTS_DIR):
            for arquivo in os.listdir(RESULTS_DIR):
                if arquivo.endswith('.txt'):
                    caminho = os.path.join(RESULTS_DIR, arquivo)
                    stat = os.stat(caminho)
                    
                    arquivos.append({
                        'nome': arquivo,
                        'tamanho': stat.st_size,
                        'data': datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
        
        # Ordenar por data de modificação (mais recente primeiro)
        arquivos.sort(key=lambda x: x['data'], reverse=True)
        
        return jsonify({'arquivos': arquivos})
        
    except Exception as e:
        logger.error(f"Erro ao listar arquivos: {e}")
        return jsonify({'arquivos': []})

@app.route('/download/<filename>')
def download_arquivo(filename):
    """Download de um arquivo específico"""
    try:
        caminho_arquivo = os.path.join(RESULTS_DIR, filename)
        
        if not os.path.exists(caminho_arquivo):
            return jsonify({'erro': 'Arquivo não encontrado'}), 404
        
        return send_file(
            caminho_arquivo,
            as_attachment=True,
            download_name=filename,
            mimetype='text/plain'
        )
        
    except Exception as e:
        logger.error(f"Erro ao fazer download: {e}")
        return jsonify({'erro': 'Erro interno'}), 500

@app.route('/download-all')
def download_all():
    """Download de todos os arquivos em um ZIP"""
    try:
        import zipfile
        
        # Criar arquivo ZIP em memória
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            if os.path.exists(RESULTS_DIR):
                for arquivo in os.listdir(RESULTS_DIR):
                    if arquivo.endswith('.txt'):
                        caminho_arquivo = os.path.join(RESULTS_DIR, arquivo)
                        zip_file.write(caminho_arquivo, arquivo)
        
        zip_buffer.seek(0)
        
        response = make_response(zip_buffer.getvalue())
        response.headers['Content-Type'] = 'application/zip'
        response.headers['Content-Disposition'] = 'attachment; filename=arquivos_extraidos.zip'
        
        return response
        
    except Exception as e:
        logger.error(f"Erro ao criar ZIP: {e}")
        return jsonify({'erro': 'Erro interno'}), 500

@app.route('/delete/<filename>', methods=['DELETE'])
def deletar_arquivo(filename):
    """Deletar um arquivo específico"""
    try:
        caminho_arquivo = os.path.join(RESULTS_DIR, filename)
        
        if not os.path.exists(caminho_arquivo):
            return jsonify({'erro': 'Arquivo não encontrado'}), 404
        
        os.remove(caminho_arquivo)
        return jsonify({'sucesso': True, 'mensagem': 'Arquivo deletado com sucesso'})
        
    except Exception as e:
        logger.error(f"Erro ao deletar arquivo: {e}")
        return jsonify({'erro': 'Erro interno'}), 500

@app.route('/excluir_arquivos', methods=['POST'])
def excluir_arquivos():
    """Exclui arquivos extraídos recentes"""
    try:
        data = request.get_json()
        dias = data.get('dias', 1)  # Padrão: excluir arquivos do último dia
        
        # Usar o diretório correto (RESULTS_DIR)
        if not os.path.exists(RESULTS_DIR):
            return jsonify({
                'sucesso': False,
                'erro': 'Diretório de arquivos não encontrado'
            })
        
        # Calcular data limite
        data_limite = datetime.now() - timedelta(days=dias)
        
        arquivos_excluidos = []
        total_arquivos = 0
        
        # Listar todos os arquivos .txt no diretório
        for arquivo in os.listdir(RESULTS_DIR):
            if arquivo.endswith('.txt'):
                caminho_arquivo = os.path.join(RESULTS_DIR, arquivo)
                total_arquivos += 1
                
                # Verificar data de modificação do arquivo
                data_modificacao = datetime.fromtimestamp(os.path.getmtime(caminho_arquivo))
                
                if data_modificacao >= data_limite:
                    try:
                        os.remove(caminho_arquivo)
                        arquivos_excluidos.append({
                            'nome': arquivo,
                            'data_modificacao': data_modificacao.strftime('%d/%m/%Y %H:%M:%S')
                        })
                    except Exception as e:
                        print(f"Erro ao excluir {arquivo}: {e}")
        
        return jsonify({
            'sucesso': True,
            'arquivos_excluidos': len(arquivos_excluidos),
            'total_arquivos': total_arquivos,
            'detalhes': arquivos_excluidos,
            'mensagem': f'{len(arquivos_excluidos)} arquivo(s) excluído(s) dos últimos {dias} dia(s)'
        })
        
    except Exception as e:
        return jsonify({
            'sucesso': False,
            'erro': f'Erro ao excluir arquivos: {str(e)}'
        })

@app.route('/listar_arquivos')
def listar_arquivos_detalhado():
    """Lista todos os arquivos extraídos com informações detalhadas"""
    try:
        arquivos = []
        
        if not os.path.exists(RESULTS_DIR):
            return jsonify({
                'sucesso': False,
                'erro': 'Diretório de arquivos não encontrado'
            })
        
        for arquivo in os.listdir(RESULTS_DIR):
            if arquivo.endswith('.txt'):
                caminho = os.path.join(RESULTS_DIR, arquivo)
                stat = os.stat(caminho)
                
                arquivos.append({
                    'nome': arquivo,
                    'tamanho': stat.st_size,
                    'data_modificacao': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'data_criacao': datetime.fromtimestamp(stat.st_ctime).isoformat()
                })
        
        # Ordenar por data de modificação (mais recente primeiro)
        arquivos.sort(key=lambda x: x['data_modificacao'], reverse=True)
        
        return jsonify({
            'sucesso': True,
            'arquivos': arquivos,
            'total': len(arquivos)
        })
        
    except Exception as e:
        return jsonify({
            'sucesso': False,
            'erro': f'Erro ao listar arquivos: {str(e)}'
        })

if __name__ == '__main__':
    print("🚀 Iniciando Extrator de Texto Web...")
    print("📱 Acesse: http://localhost:5000")
    print("📁 Resultados salvos em:", os.path.abspath(RESULTS_DIR))
    app.run(debug=True, host='0.0.0.0', port=5000)

# Handler para Vercel (WSGI compatibility)
app.wsgi_app = app.wsgi_app