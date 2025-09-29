// Configurações da aplicação
const CONFIG = {
    API_BASE_URL: 'http://localhost:5000',
    ENDPOINTS: {
        EXTRACT: '/extrair',
        FILES: '/arquivos',
        DOWNLOAD: '/download',
        DELETE: '/delete',
        DELETE_FILES: '/excluir_arquivos',
        LIST_FILES: '/listar_arquivos'
    },
    POLLING_INTERVAL: 2000,
    MAX_FILES_LIMIT: 10 // Limite máximo de arquivos aumentado
};

// Estado da aplicação
const AppState = {
    isExtracting: false,
    currentFiles: [],
    retryCount: 0
};

// Elementos DOM
const elements = {
    form: document.getElementById('extractionForm'),
    urlInput: document.getElementById('urlInput'),
    extractBtn: document.getElementById('extractBtn'),
    statusMessage: document.getElementById('statusMessage'),
    resultsSection: document.getElementById('resultsSection'),
    filesList: document.getElementById('filesList'),
    refreshBtn: document.getElementById('refreshBtn'),
    deleteFilesBtn: document.getElementById('deleteFilesBtn')
};

// Utilitários
const Utils = {
    // Validar URL
    isValidUrl: (string) => {
        try {
            new URL(string);
            return true;
        } catch (_) {
            return false;
        }
    },

    // Formatar tamanho de arquivo
    formatFileSize: (bytes) => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    // Debounce para otimizar performance
    debounce: (func, wait) => {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // Mostrar notificação toast
    showToast: (message, type = 'info') => {
        // Implementação simples de toast
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 24px;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            z-index: 1000;
            animation: slideInRight 0.3s ease-out;
            max-width: 300px;
        `;
        
        const colors = {
            success: '#10b981',
            error: '#ef4444',
            warning: '#f59e0b',
            info: '#3b82f6'
        };
        
        toast.style.backgroundColor = colors[type] || colors.info;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideOutRight 0.3s ease-in';
            setTimeout(() => document.body.removeChild(toast), 300);
        }, 3000);
    }
};

// Gerenciador de UI
const UIManager = {
    // Mostrar status de carregamento
    showLoading: (message = 'Processando...') => {
        elements.statusMessage.innerHTML = `
            <div class="loading-content">
                <div class="loading-spinner"></div>
                <span>${message}</span>
            </div>
        `;
        elements.statusMessage.className = 'status-message loading';
        elements.extractBtn.disabled = true;
        elements.extractBtn.innerHTML = '<div class="loading-spinner"></div> Extraindo...';
    },

    // Mostrar mensagem de sucesso
    showSuccess: (message) => {
        elements.statusMessage.textContent = message;
        elements.statusMessage.className = 'status-message success';
        elements.extractBtn.disabled = false;
        elements.extractBtn.innerHTML = '<i class="fas fa-download"></i> Extrair Texto';
    },

    // Mostrar mensagem de erro
    showError: (message) => {
        elements.statusMessage.textContent = message;
        elements.statusMessage.className = 'status-message error';
        elements.extractBtn.disabled = false;
        elements.extractBtn.innerHTML = '<i class="fas fa-download"></i> Extrair Texto';
    },

    // Ocultar mensagem de status
    hideStatus: () => {
        elements.statusMessage.style.display = 'none';
        elements.statusMessage.className = 'status-message';
    },

    // Renderizar lista de arquivos
    renderFilesList: (files) => {
        if (!files || files.length === 0) {
            elements.resultsSection.style.display = 'none';
            return;
        }

        elements.resultsSection.style.display = 'block';
        elements.filesList.innerHTML = files.map(file => `
            <div class="file-item" data-filename="${file.nome}">
                <div class="file-info">
                    <i class="fas fa-file-text"></i>
                    <div>
                        <div class="file-name">${file.nome}</div>
                        <div class="file-size">${Utils.formatFileSize(file.tamanho)}</div>
                    </div>
                </div>
                <button class="download-btn" onclick="FileManager.downloadFile('${file.nome}')">
                    <i class="fas fa-download"></i> Download
                </button>
            </div>
        `).join('');
    },

    // Adicionar animações suaves aos cards
    animateCards: () => {
        const cards = document.querySelectorAll('.card');
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }
            });
        }, { threshold: 0.1 });

        cards.forEach(card => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(30px)';
            card.style.transition = 'all 0.6s ease-out';
            observer.observe(card);
        });
    }
};

// Gerenciador de arquivos
const FileManager = {
    // Buscar lista de arquivos
    fetchFiles: async () => {
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.ENDPOINTS.FILES}`);
            if (!response.ok) throw new Error('Erro ao buscar arquivos');
            
            const data = await response.json();
            AppState.currentFiles = data.arquivos || [];
            UIManager.renderFilesList(AppState.currentFiles);
            
            return AppState.currentFiles;
        } catch (error) {
            console.error('Erro ao buscar arquivos:', error);
            Utils.showToast('Erro ao carregar lista de arquivos', 'error');
            return [];
        }
    },

    // Verificar e excluir arquivos automaticamente se exceder o limite
    checkAndDeleteExcessFiles: async () => {
        try {
            const files = await FileManager.fetchFiles();
            
            if (files.length > CONFIG.MAX_FILES_LIMIT) {
                const excessCount = files.length - CONFIG.MAX_FILES_LIMIT;
                console.log(`Limite de ${CONFIG.MAX_FILES_LIMIT} arquivos excedido. Excluindo ${excessCount} arquivo(s) mais antigo(s)...`);
                
                // Ordenar arquivos por data de modificação (mais antigos primeiro)
                const sortedFiles = files.sort((a, b) => {
                    const dateA = new Date(a.data_modificacao || 0);
                    const dateB = new Date(b.data_modificacao || 0);
                    return dateA - dateB;
                });
                
                // Excluir os arquivos mais antigos
                const filesToDelete = sortedFiles.slice(0, excessCount);
                
                for (const file of filesToDelete) {
                    try {
                        await FileManager.deleteFile(file.nome);
                        console.log(`Arquivo ${file.nome} excluído automaticamente`);
                    } catch (error) {
                        console.error(`Erro ao excluir arquivo ${file.nome}:`, error);
                    }
                }
                
                Utils.showToast(`${excessCount} arquivo(s) antigo(s) excluído(s) automaticamente`, 'info');
                
                // Atualizar lista após exclusões
                await FileManager.fetchFiles();
            }
        } catch (error) {
            console.error('Erro ao verificar limite de arquivos:', error);
        }
    },

    // Download de arquivo específico
    downloadFile: async (filename) => {
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.ENDPOINTS.DOWNLOAD}/${filename}`);
            if (!response.ok) throw new Error('Erro no download');

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            Utils.showToast(`Download de ${filename} concluído!`, 'success');
        } catch (error) {
            console.error('Erro no download:', error);
            Utils.showToast('Erro ao fazer download do arquivo', 'error');
        }
    },

    // Deletar arquivo
    deleteFile: async (filename) => {
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.ENDPOINTS.DELETE}/${filename}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) throw new Error('Erro ao deletar arquivo');
            
            Utils.showToast(`Arquivo ${filename} deletado com sucesso!`, 'success');
            await FileManager.fetchFiles(); // Atualizar lista
        } catch (error) {
            console.error('Erro ao deletar arquivo:', error);
            Utils.showToast('Erro ao deletar arquivo', 'error');
        }
    },

    // Excluir arquivos recentes
    deleteRecentFiles: async (days = 1) => {
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.ENDPOINTS.DELETE_FILES}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ dias: days })
            });
            
            if (!response.ok) throw new Error('Erro ao excluir arquivos');
            
            const data = await response.json();
            
            if (data.sucesso) {
                Utils.showToast(data.mensagem, 'success');
                await FileManager.fetchFiles(); // Atualizar lista
            } else {
                throw new Error(data.erro);
            }
        } catch (error) {
            console.error('Erro ao excluir arquivos:', error);
            Utils.showToast('Erro ao excluir arquivos', 'error');
        }
    },

    // Listar arquivos com informações detalhadas
    listFiles: async () => {
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.ENDPOINTS.LIST_FILES}`);
            if (!response.ok) throw new Error('Erro ao listar arquivos');
            
            const data = await response.json();
            
            if (data.sucesso) {
                AppState.currentFiles = data.arquivos || [];
                UIManager.renderFilesList(AppState.currentFiles);
                return data;
            } else {
                throw new Error(data.erro);
            }
        } catch (error) {
            console.error('Erro ao listar arquivos:', error);
            Utils.showToast('Erro ao carregar arquivos', 'error');
            return null;
        }
    }
};

// Gerenciador de extração
const ExtractionManager = {
    // Extrair texto de uma URL
    extractText: async (url) => {
        if (AppState.isExtracting) return;
        
        AppState.isExtracting = true;
        
        try {
            UIManager.showLoading('Iniciando extração...');
            
            const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.ENDPOINTS.EXTRACT}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url: url })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.erro || 'Erro na extração');
            }

            if (data.sucesso) {
                UIManager.showSuccess('Extração concluída com sucesso!');
                Utils.showToast('Texto extraído com sucesso!', 'success');
                
                // Atualizar lista de arquivos
                setTimeout(async () => {
                    await FileManager.fetchFiles();
                    await FileManager.checkAndDeleteExcessFiles();
                }, 1000);
            } else {
                throw new Error(data.erro || 'Erro desconhecido na extração');
            }

        } catch (error) {
            console.error('Erro na extração:', error);
            UIManager.showError(`Erro: ${error.message}`);
            Utils.showToast('Erro na extração do texto', 'error');
            
            // Tratamento específico para erros de configuração
            if (error.message.includes('WinError 193')) {
                UIManager.showError('Erro de configuração do Chrome WebDriver. Verifique se o Chrome está instalado corretamente.');
                Utils.showToast('Erro de configuração do sistema', 'error');
            }
        } finally {
            AppState.isExtracting = false;
        }
    }
};

// Event Listeners
const EventHandlers = {
    // Inicializar eventos
    init: () => {
        // Evento de submit do formulário
        elements.form.addEventListener('submit', EventHandlers.handleFormSubmit);
        
        // Validação em tempo real da URL
        elements.urlInput.addEventListener('input', Utils.debounce(EventHandlers.handleUrlInput, 300));
        
        // Eventos de teclado
        elements.urlInput.addEventListener('keydown', EventHandlers.handleKeyDown);
        
        // Botões de ação
        if (elements.refreshBtn) {
            elements.refreshBtn.addEventListener('click', EventHandlers.handleRefreshFiles);
        }
        
        if (elements.deleteFilesBtn) {
            elements.deleteFilesBtn.addEventListener('click', EventHandlers.handleDeleteFiles);
        }
        
        // Eventos dos cards (hover effects)
        document.querySelectorAll('.card').forEach(card => {
            card.addEventListener('mouseenter', EventHandlers.handleCardHover);
            card.addEventListener('mouseleave', EventHandlers.handleCardLeave);
        });
    },

    // Manipular submit do formulário
    handleFormSubmit: async (e) => {
        e.preventDefault();
        
        const url = elements.urlInput.value.trim();
        
        if (!url) {
            Utils.showToast('Por favor, insira uma URL', 'warning');
            elements.urlInput.focus();
            return;
        }
        
        if (!Utils.isValidUrl(url)) {
            Utils.showToast('Por favor, insira uma URL válida', 'error');
            elements.urlInput.focus();
            return;
        }
        
        await ExtractionManager.extractText(url);
    },

    // Validação da URL em tempo real
    handleUrlInput: (e) => {
        const url = e.target.value.trim();
        const isValid = !url || Utils.isValidUrl(url);
        
        e.target.style.borderColor = isValid ? '' : 'var(--error-color)';
        
        if (!isValid && url) {
            e.target.style.boxShadow = '0 0 0 3px rgb(239 68 68 / 0.1)';
        } else {
            e.target.style.boxShadow = '';
        }
    },

    // Manipular teclas especiais
    handleKeyDown: (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            elements.form.dispatchEvent(new Event('submit'));
        }
    },

    // Efeitos de hover nos cards
    handleCardHover: (e) => {
        const card = e.currentTarget;
        card.style.transform = 'translateY(-8px) scale(1.02)';
    },

    handleCardLeave: (e) => {
        const card = e.currentTarget;
        card.style.transform = '';
    },

    // Manipular atualização de arquivos
    handleRefreshFiles: async (e) => {
        e.preventDefault();
        const btn = e.currentTarget;
        const icon = btn.querySelector('i');
        
        // Animação de loading
        btn.disabled = true;
        icon.style.animation = 'spin 1s linear infinite';
        
        try {
            await FileManager.listFiles();
            Utils.showToast('Lista atualizada!', 'success');
        } catch (error) {
            Utils.showToast('Erro ao atualizar lista', 'error');
        } finally {
            btn.disabled = false;
            icon.style.animation = '';
        }
    },

    // Manipular exclusão de arquivos
    handleDeleteFiles: async (e) => {
        e.preventDefault();
        
        const confirmDelete = confirm('Deseja excluir todos os arquivos extraídos do último dia?');
        if (!confirmDelete) return;
        
        const btn = e.currentTarget;
        const originalText = btn.innerHTML;
        
        // Estado de loading
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Excluindo...';
        
        try {
            await FileManager.deleteRecentFiles(1);
        } catch (error) {
            Utils.showToast('Erro ao excluir arquivos', 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }
};

// Inicialização da aplicação
const App = {
    // Inicializar aplicação
    init: async () => {
        try {
            // Configurar eventos
            EventHandlers.init();
            
            // Carregar arquivos existentes
            await FileManager.fetchFiles();
            
            // Inicializar animações
            UIManager.animateCards();
            
            // Adicionar estilos CSS dinâmicos
            App.addDynamicStyles();
            
            console.log('✅ Aplicação inicializada com sucesso');
            
        } catch (error) {
            console.error('❌ Erro na inicialização:', error);
            Utils.showToast('Erro na inicialização da aplicação', 'error');
        }
    },

    // Adicionar estilos CSS dinâmicos
    addDynamicStyles: () => {
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideInRight {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            
            @keyframes slideOutRight {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
            
            .loading-content {
                display: flex;
                align-items: center;
                gap: 12px;
                justify-content: center;
            }
            
            .file-name {
                font-weight: 500;
                color: var(--gray-800);
            }
            
            .file-size {
                font-size: var(--font-size-xs);
                color: var(--gray-500);
                margin-top: 2px;
            }
            
            .card {
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }
            
            .url-input:invalid {
                border-color: var(--error-color);
                box-shadow: 0 0 0 3px rgb(239 68 68 / 0.1);
            }
        `;
        document.head.appendChild(style);
    }
};

// Expor funções globais necessárias
window.FileManager = FileManager;
window.ExtractionManager = ExtractionManager;

// Inicializar quando o DOM estiver carregado
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', App.init);
} else {
    App.init();
}

// Service Worker para cache (opcional)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        // Implementação futura do service worker
        console.log('Service Worker disponível para implementação futura');
    });
}