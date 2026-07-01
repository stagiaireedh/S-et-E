/**
 * Application de Suivi-Évaluation - Triangulation de Données
 * Logique Frontend JavaScript - S&E-CSB
 */

document.addEventListener('DOMContentLoaded', () => {
    // --- VARIABLES DE L'APPLICATION ---
    let currentUser = null;
    let activeProjectId = null;
    let activeQuestionnaireId = null;
    let projects = [];
    let questionnaires = [];
    let charts = {}; // Stockage des instances de Chart.js pour pouvoir les mettre à jour
    let editingSessionId = null; // Session ID en cours d'édition
    
    // --- UTILS : TOASTS & INDICATEURS DE CHARGEMENT ---
    function showToast(message, type = 'success') {
        const container = document.getElementById('toast-container');
        if (!container) return;
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        let icon = 'ℹ️';
        if (type === 'success') icon = '✅';
        else if (type === 'error') icon = '❌';
        else if (type === 'warning') icon = '⚠️';
        
        toast.innerHTML = `
            <span class="toast-icon">${icon}</span>
            <span class="toast-message">${message}</span>
        `;
        
        container.appendChild(toast);
        
        // Force reflow
        setTimeout(() => toast.classList.add('show'), 10);
        
        // Auto-remove
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 400);
        }, 4000);
    }
    
    function showLoader() {
        const loader = document.getElementById('loader');
        if (loader) loader.style.display = 'flex';
    }
    
    // Rendre accessible globalement pour les scripts d'analyse IA
    window.showLoader = showLoader;
    
    function hideLoader() {
        const loader = document.getElementById('loader');
        if (loader) loader.style.display = 'none';
    }
    
    window.hideLoader = hideLoader;
    
    // --- CENTRALISATION DES APPELS API AVEC CACHE ET SYNC ---
    const apiCache = new Map();
    
    async function requestAPI(url, options = {}) {
        const method = options.method || 'GET';
        const silent = options.silent || false;
        
        if (method === 'GET') {
            if (apiCache.has(url)) {
                return apiCache.get(url);
            }
            showLoader();
            try {
                const res = await fetch(url, options);
                
                // Si l'utilisateur perd sa session ou n'est pas connecté
                if (res.status === 401 && !url.includes('/api/me')) {
                    currentUser = null;
                    document.getElementById('auth-overlay').style.display = 'flex';
                    document.getElementById('app-workspace').style.display = 'none';
                    throw new Error("Authentification requise.");
                }
                
                if (!res.ok) {
                    const errData = await res.json().catch(() => ({}));
                    throw new Error(errData.message || `Erreur HTTP ${res.status}`);
                }
                const data = await res.json();
                apiCache.set(url, data);
                return data;
            } catch (err) {
                if (err.message !== "Authentification requise." && !silent) {
                    showToast(`Erreur de chargement : ${err.message}`, 'error');
                }
                throw err;
            } finally {
                hideLoader();
            }
        } else {
            showLoader();
            try {
                const res = await fetch(url, options);
                
                if (res.status === 401) {
                    currentUser = null;
                    document.getElementById('auth-overlay').style.display = 'flex';
                    document.getElementById('app-workspace').style.display = 'none';
                    throw new Error("Authentification requise.");
                }
                
                if (!res.ok) {
                    const errData = await res.json().catch(() => ({}));
                    throw new Error(errData.message || `Erreur HTTP ${res.status}`);
                }
                const data = await res.json();
                
                // Vider le cache sur toute écriture
                apiCache.clear();
                
                // Déclencher la synchronisation en temps réel (custom event)
                document.dispatchEvent(new CustomEvent('dataChanged', { detail: { action: method, url } }));
                
                return data;
            } catch (err) {
                if (err.message !== "Authentification requise." && !silent) {
                    showToast(`Erreur de traitement : ${err.message}`, 'error');
                }
                throw err;
            } finally {
                hideLoader();
            }
        }
    }

    // --- MODALE DE CONFIRMATION DE SUPPRESSION ---
    let deleteConfirmCallback = null;
    
    function openConfirmModal(itemName, message, onConfirm) {
        const modal = document.getElementById('modal-confirm-delete');
        const textEl = document.getElementById('confirm-modal-text');
        const nameEl = document.getElementById('confirm-modal-item-name');
        
        textEl.innerText = message || "Êtes-vous sûr de vouloir supprimer cet élément ?";
        nameEl.innerText = itemName;
        
        deleteConfirmCallback = onConfirm;
        modal.classList.add('active');
    }
    
    document.getElementById('btn-confirm-delete').addEventListener('click', () => {
        if (deleteConfirmCallback) {
            deleteConfirmCallback();
            deleteConfirmCallback = null;
        }
        document.getElementById('modal-confirm-delete').classList.remove('active');
    });
    
    const closeConfirmModal = () => {
        deleteConfirmCallback = null;
        document.getElementById('modal-confirm-delete').classList.remove('active');
    };
    
    document.getElementById('btn-close-confirm-modal').addEventListener('click', closeConfirmModal);
    document.getElementById('btn-cancel-delete').addEventListener('click', closeConfirmModal);
    
    // --- ÉLÉMENTS DU DOM ---
    // Sélecteurs principaux
    const projectSelect = document.getElementById('global-project-select');
    const projectTitle = document.getElementById('current-project-title');
    const projectDesc = document.getElementById('current-project-desc');
    
    // Onglets
    const navItems = document.querySelectorAll('.nav-item');
    const tabPanes = document.querySelectorAll('.tab-pane');
    
    // Boutons Actions
    const btnNewProject = document.getElementById('btn-new-project');
    const btnExportGlobalPdf = document.getElementById('btn-export-global-pdf');
    const btnQuickSaisie = document.getElementById('btn-quick-saisie');
    const btnCreateQuestionnaire = document.getElementById('btn-create-questionnaire');
    
    // Modals
    const modalProject = document.getElementById('modal-project');
    const modalCreateQuestionnaireSelect = document.getElementById('modal-create-questionnaire-select');
    const modalImportQuestionnaire = document.getElementById('modal-import-questionnaire');
    const modalAiAssistantQuest = document.getElementById('modal-ai-assistant-quest');
    
    // Formulaires
    const formNewProject = document.getElementById('form-new-project');
    const formSelectTemplateCreate = document.getElementById('form-select-template-create');
    const formInterviewSaisie = document.getElementById('form-interview-saisie');
    
    // Collecte & Saisie
    const selectQuestionnaire = document.getElementById('collecte-questionnaire-select');
    const saisieQuestionnaireId = document.getElementById('saisie-questionnaire-id');
    const dynamicQuestionsContainer = document.getElementById('dynamic-questions-container');
    const btnSubmitSaisie = document.getElementById('btn-submit-saisie');
    const btnEditActiveQuest = document.getElementById('btn-edit-active-questionnaire');

    // --- 1. GESTION DES ONGLETS ---
    function switchTab(tabId) {
        // Mettre à jour la navigation active
        navItems.forEach(item => {
            if (item.getAttribute('data-tab') === tabId) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
        
        // Afficher le bon volet
        tabPanes.forEach(pane => {
            if (pane.id === `tab-${tabId}`) {
                pane.classList.add('active');
            } else {
                pane.classList.remove('active');
            }
        });
        
        // Logique spécifique par onglet ouvert
        if (tabId === 'dashboard') {
            loadDashboardData();
        } else if (tabId === 'collecte') {
            loadQuestionnairesList();
        } else if (tabId === 'analyse') {
            loadTriangulationData();
        }
    }
    
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const tabId = item.getAttribute('data-tab');
            switchTab(tabId);
            window.location.hash = tabId;
        });
    });
    
    // Gestion du hash initial dans l'URL
    if (window.location.hash) {
        const initialTab = window.location.hash.substring(1);
        const tabExists = Array.from(navItems).some(item => item.getAttribute('data-tab') === initialTab);
        if (tabExists) switchTab(initialTab);
    }

    // --- 2. GESTION DES PROJETS ---
    async function loadProjects(selectDefault = true) {
        try {
            projects = await requestAPI('/api/projects');
            
            projectSelect.innerHTML = '';
            if (projects.length === 0) {
                projectSelect.innerHTML = '<option value="" disabled selected>Créer un projet d\'abord</option>';
                activeProjectId = null;
                updateActiveProjectDetails();
                return;
            }
            
            projects.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.id;
                opt.innerText = p.name;
                projectSelect.appendChild(opt);
            });
            
            if (selectDefault) {
                const savedProjectId = localStorage.getItem('activeProjectId');
                if (savedProjectId && projects.some(p => p.id == savedProjectId)) {
                    activeProjectId = parseInt(savedProjectId);
                } else {
                    activeProjectId = projects[0].id;
                }
            }
            
            projectSelect.value = activeProjectId;
            updateActiveProjectDetails();
        } catch (err) {
            console.error("Erreur de chargement des projets:", err);
        }
    }
    
    function updateActiveProjectDetails() {
        const proj = projects.find(p => p.id === activeProjectId);
        if (proj) {
            projectTitle.innerText = proj.name;
            projectDesc.innerText = proj.description || "Aucune description.";
            localStorage.setItem('activeProjectId', activeProjectId);

            const btnDeleteProject = document.getElementById('btn-delete-project');
            const btnCreateQuestionnaire = document.getElementById('btn-create-questionnaire');
            
            if (btnDeleteProject) btnDeleteProject.style.display = 'inline-flex';
            if (btnCreateQuestionnaire) {
                btnCreateQuestionnaire.disabled = false;
                btnCreateQuestionnaire.title = "";
            }
        } else {
            projectTitle.innerText = "Aucun projet";
            projectDesc.innerText = "Aucun projet, créez-en un.";
            localStorage.removeItem('activeProjectId');
            
            const btnDeleteProject = document.getElementById('btn-delete-project');
            const btnCreateQuestionnaire = document.getElementById('btn-create-questionnaire');
            if (btnDeleteProject) btnDeleteProject.style.display = 'none';
            if (btnCreateQuestionnaire) btnCreateQuestionnaire.disabled = false;
        }
    }
    
    projectSelect.addEventListener('change', (e) => {
        activeProjectId = parseInt(e.target.value);
        updateActiveProjectDetails();
        
        // Recharger les données de l'onglet actif
        const activeTab = document.querySelector('.nav-item.active').getAttribute('data-tab');
        switchTab(activeTab);
    });
    
    // Suppression de Projet
    async function deleteActiveProject() {
        if (!activeProjectId) return;
        const proj = projects.find(p => p.id === activeProjectId);
        if (!proj) return;
        
        openConfirmModal(
            proj.name,
            "Êtes-vous sûr de vouloir supprimer ce projet ? Cette action supprimera définitivement le projet, tous les questionnaires, tous les entretiens et toutes les réponses de triangulation associés.",
            async () => {
                try {
                    const res = await requestAPI(`/api/projects/${activeProjectId}`, { method: 'DELETE' });
                    if (res.success) {
                        showToast("Projet supprimé avec succès !", "success");
                        localStorage.removeItem('activeProjectId');
                        activeProjectId = null;
                        await loadProjects(true);
                        switchTab('dashboard');
                    }
                } catch (err) {
                    console.error("Erreur de suppression du projet:", err);
                }
            }
        );
    }
    
    const btnDeleteProject = document.getElementById('btn-delete-project');
    if (btnDeleteProject) {
        btnDeleteProject.addEventListener('click', deleteActiveProject);
    }
    
    // Modals Projet
    btnNewProject.addEventListener('click', () => modalProject.classList.add('active'));
    document.getElementById('btn-close-project-modal').addEventListener('click', () => modalProject.classList.remove('active'));
    document.getElementById('btn-cancel-project-modal').addEventListener('click', () => modalProject.classList.remove('active'));
    
    formNewProject.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('new-project-name').value;
        const description = document.getElementById('new-project-desc').value;
        
        if (name && name.length > 255) {
            showToast("Le nom du projet ne doit pas dépasser 255 caractères.", "warning");
            return;
        }
        
        try {
            const result = await requestAPI('/api/projects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, description })
            });
            if (result.success) {
                modalProject.classList.remove('active');
                formNewProject.reset();
                showToast("Projet créé avec succès !", "success");
                localStorage.setItem('activeProjectId', result.project.id);
                await loadProjects(true);
            }
        } catch (err) {
            console.error("Erreur lors de la création du projet:", err);
        }
    });

    // --- 3. RAPPORT GLOBAL PDF ---
    btnExportGlobalPdf.addEventListener('click', () => {
        if (!activeProjectId) return;
        window.open(`/api/projects/${activeProjectId}/report`, '_blank');
    });

    // --- 4. TABLEAU DE BORD (DASHBOARD) ---
    async function loadDashboardData() {
        if (!activeProjectId) {
            document.getElementById('kpi-total-sessions').innerText = "0";
            document.getElementById('kpi-total-questionnaires').innerText = "0";
            document.getElementById('kpi-total-attachments').innerText = "0";
            document.getElementById('kpi-sentiment-avg').innerText = "-";
            document.querySelector('#table-recent-sessions tbody').innerHTML = '<tr><td colspan="6" class="text-center text-muted">Veuillez d\'abord créer un projet.</td></tr>';
            renderAttachments([]);
            renderDashboardCharts([]);
            return;
        }
        
        try {
            const sessions = await requestAPI(`/api/projects/${activeProjectId}/sessions`);
            const quests = await requestAPI(`/api/projects/${activeProjectId}/questionnaires`);
            const attachments = await requestAPI(`/api/projects/${activeProjectId}/attachments`);
            
            document.getElementById('kpi-total-sessions').innerText = sessions.length;
            document.getElementById('kpi-total-questionnaires').innerText = quests.length;
            document.getElementById('kpi-total-attachments').innerText = attachments.length;
            
            try {
                const triang = await requestAPI(`/api/projects/${activeProjectId}/triangulation`, { silent: true });
                if (triang.success) {
                    const score = triang.avg_sentiment_score;
                    const label = triang.sentiment_label.toUpperCase();
                    document.getElementById('kpi-sentiment-avg').innerText = `${score} (${label})`;
                } else {
                    document.getElementById('kpi-sentiment-avg').innerText = "-";
                }
            } catch {
                document.getElementById('kpi-sentiment-avg').innerText = "-";
            }
            
            // Remplir le tableau des entretiens récents
            const tbody = document.querySelector('#table-recent-sessions tbody');
            tbody.innerHTML = '';
            
            if (sessions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Aucun entretien enregistré.</td></tr>';
            } else {
                sessions.slice(0, 5).forEach(s => {
                    const tr = document.createElement('tr');
                    
                    let individualScore = 0;
                    if (s.answers.length > 0) {
                        const scoreSum = s.answers.reduce((acc, a) => {
                            const txt = a.answer_text.toLowerCase();
                            if (txt.includes('panne') || txt.includes('difficile') || txt.includes('problème') || txt.includes('défaut')) return acc - 0.5;
                            if (txt.includes('bon') || txt.includes('excellent') || txt.includes('très bien') || txt.includes('satisfait')) return acc + 0.5;
                            return acc;
                        }, 0);
                        individualScore = scoreSum / s.answers.length;
                    }
                    
                    let badgeClass = 'badge-info';
                    let interpretLabel = 'Neutre';
                    if (individualScore > 0.15) {
                        badgeClass = 'badge-success';
                        interpretLabel = 'Positif';
                    } else if (individualScore < -0.15) {
                        badgeClass = 'badge-danger';
                        interpretLabel = 'Négatif';
                    }
                    
                    const dateObj = new Date(s.interview_date);
                    const formattedDate = dateObj.toLocaleDateString('fr-FR');
                    
                    tr.innerHTML = `
                        <td>${formattedDate}</td>
                        <td><strong>${s.title}</strong><br><small class="text-muted">${s.interviewee_name_or_group}</small></td>
                        <td>${s.actor_category}</td>
                        <td><span class="badge ${s.session_type === 'collectif' ? 'badge-warning' : 'badge-info'}">${s.session_type}</span></td>
                        <td><span class="badge ${badgeClass}">${interpretLabel}</span></td>
                        <td>
                            <div class="table-actions">
                                <button class="btn-link btn-download-session-pdf" data-id="${s.id}" title="Télécharger Fiche PDF">
                                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
                                </button>
                                <button class="btn-link btn-edit-session" data-id="${s.id}" title="Modifier l'Entretien">
                                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7M18.5 2.5a2.121 2.121 0 1 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                                </button>
                                <button class="btn-link btn-delete-session" data-id="${s.id}" data-name="${s.title}" title="Supprimer l'Entretien">
                                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
                                </button>
                            </div>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
                
                document.querySelectorAll('.btn-download-session-pdf').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        const sId = btn.getAttribute('data-id');
                        window.open(`/api/sessions/${sId}/report`, '_blank');
                    });
                });

                document.querySelectorAll('.btn-edit-session').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        const sId = btn.getAttribute('data-id');
                        editSession(parseInt(sId));
                    });
                });

                document.querySelectorAll('.btn-delete-session').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        const sId = btn.getAttribute('data-id');
                        const sName = btn.getAttribute('data-name');
                        deleteSession(parseInt(sId), sName);
                    });
                });
            }
            
            renderAttachments(attachments);
            renderDashboardCharts(sessions);
        } catch (err) {
            console.error("Erreur de chargement du dashboard:", err);
        }
    }
    
    btnQuickSaisie.addEventListener('click', () => switchTab('collecte'));
    
    // --- 5. RENDER DES GRAPHIQUES (CHART.JS) ---
    function renderDashboardCharts(sessions) {
        const actorCounts = {
            'Bénéficiaire': 0,
            'Partenaire': 0,
            'Équipe Projet': 0,
            'Autorité Locale': 0
        };
        
        sessions.forEach(s => {
            if (actorCounts[s.actor_category] !== undefined) {
                actorCounts[s.actor_category]++;
            }
        });
        
        const ctxActors = document.getElementById('chart-actors-distribution').getContext('2d');
        if (charts.actors) charts.actors.destroy();
        
        charts.actors = new Chart(ctxActors, {
            type: 'doughnut',
            data: {
                labels: Object.keys(actorCounts),
                datasets: [{
                    data: Object.values(actorCounts),
                    backgroundColor: ['#6366f1', '#06b6d4', '#a855f7', '#ec4899'],
                    borderColor: 'rgba(7, 9, 19, 0.6)',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#94a3b8', font: { family: 'Outfit', size: 12 } }
                    }
                }
            }
        });
        
        const sortedSessions = [...sessions].sort((a, b) => new Date(a.interview_date) - new Date(b.interview_date));
        const chartLabels = [];
        const chartData = [];
        
        sortedSessions.forEach(s => {
            const dateObj = new Date(s.interview_date);
            chartLabels.push(dateObj.toLocaleDateString('fr-FR', { month: 'short', day: 'numeric' }));
            
            let score = 0;
            if (s.answers.length > 0) {
                const scoreSum = s.answers.reduce((acc, a) => {
                    const txt = a.answer_text.toLowerCase();
                    if (txt.includes('panne') || txt.includes('difficile') || txt.includes('problème') || txt.includes('défaut')) return acc - 0.5;
                    if (txt.includes('bon') || txt.includes('excellent') || txt.includes('très bien') || txt.includes('satisfait')) return acc + 0.5;
                    return acc;
                }, 0);
                score = scoreSum / s.answers.length;
            }
            chartData.push(score);
        });
        
        const ctxSentiment = document.getElementById('chart-sentiments-trend').getContext('2d');
        if (charts.sentiment) charts.sentiment.destroy();
        
        charts.sentiment = new Chart(ctxSentiment, {
            type: 'line',
            data: {
                labels: chartLabels,
                datasets: [{
                    label: 'Sentiment (Individuel)',
                    data: chartData,
                    borderColor: '#06b6d4',
                    backgroundColor: 'rgba(6, 182, 212, 0.1)',
                    tension: 0.3,
                    fill: true,
                    borderWidth: 3,
                    pointBackgroundColor: '#6366f1',
                    pointHoverRadius: 7
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: {
                        min: -1,
                        max: 1,
                        ticks: { color: '#94a3b8' },
                        grid: { color: 'rgba(255, 255, 255, 0.05)' }
                    },
                    x: {
                        ticks: { color: '#94a3b8' },
                        grid: { display: false }
                    }
                }
            }
        });
    }

    // --- 6. DRAG AND DROP & UPLOADS DE PIÈCES JOINTES ---
    const dropZone = document.getElementById('file-drop-area');
    const fileInput = document.getElementById('file-upload-input');
    
    fileInput.addEventListener('click', (e) => e.stopPropagation());
    
    dropZone.addEventListener('click', (e) => {
        if (e.target === fileInput) return;
        if (!activeProjectId) {
            showToast("Veuillez d'abord sélectionner ou créer un projet.", "warning");
            return;
        }
        fileInput.click();
    });
    
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        if (!activeProjectId) return;
        dropZone.classList.add('dragover');
    });
    
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });
    
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        if (!activeProjectId) {
            showToast("Veuillez d'abord sélectionner ou créer un projet.", "warning");
            return;
        }
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            uploadFiles(files);
        }
    });
    
    fileInput.addEventListener('change', (e) => {
        const files = e.target.files;
        if (files.length > 0) {
            uploadFiles(files);
        }
    });
    
    async function uploadFiles(files) {
        if (!activeProjectId) return;
        
        let successCount = 0;
        for (let i = 0; i < files.length; i++) {
            const formData = new FormData();
            formData.append('file', files[i]);
            
            try {
                const result = await requestAPI(`/api/projects/${activeProjectId}/attachments`, {
                    method: 'POST',
                    body: formData
                });
                if (result.success) {
                    successCount++;
                }
            } catch (err) {
                console.error("Erreur d'upload:", err);
            }
        }
        
        if (successCount > 0) {
            showToast(`${successCount} fichier(s) joint(s) téléversé(s) avec succès !`, "success");
            await loadDashboardData();
        }
    }
    
    function renderAttachments(attachments) {
        const container = document.getElementById('attachments-container-list');
        container.innerHTML = '';
        
        if (attachments.length === 0) {
            container.innerHTML = '<p class="text-muted text-center py-2">Aucune pièce jointe.</p>';
            return;
        }
        
        attachments.forEach(att => {
            const div = document.createElement('div');
            div.className = 'attachment-item';
            
            div.innerHTML = `
                <div class="attachment-info">
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <span>${att.filename}</span>
                </div>
                <a href="/uploads/${att.filepath}" target="_blank" class="btn-link">Visualiser</a>
            `;
            container.appendChild(div);
        });
    }

    // --- 7. ONGLET COLLECTE & CREATION QUESTIONNAIRE ---

    async function loadQuestionnairesList() {
        if (!activeProjectId) {
            selectQuestionnaire.innerHTML = '<option value="" disabled selected>Créer un projet d\'abord...</option>';
            const btnShare = document.getElementById('btn-share-questionnaire');
            if (btnShare) btnShare.style.display = 'none';
            if (btnEditActiveQuest) btnEditActiveQuest.style.display = 'none';
            return;
        }
        
        try {
            questionnaires = await requestAPI(`/api/projects/${activeProjectId}/questionnaires`);
            
            selectQuestionnaire.innerHTML = '<option value="" disabled selected>Choisir un questionnaire...</option>';
            questionnaires.forEach(q => {
                const opt = document.createElement('option');
                opt.value = q.id;
                opt.innerText = q.title;
                selectQuestionnaire.appendChild(opt);
            });
            
            if (activeQuestionnaireId) {
                selectQuestionnaire.value = activeQuestionnaireId;
                renderQuestionsFields();
                if (btnEditActiveQuest) btnEditActiveQuest.style.display = 'block';
            } else {
                if (btnEditActiveQuest) btnEditActiveQuest.style.display = 'none';
            }
        } catch (err) {
            console.error("Erreur chargement questionnaires:", err);
        }
    }
    
    selectQuestionnaire.addEventListener('change', (e) => {
        activeQuestionnaireId = parseInt(e.target.value);
        saisieQuestionnaireId.value = activeQuestionnaireId;
        renderQuestionsFields();
        
        // Afficher/masquer le bouton de partage de questionnaire
        const btnShare = document.getElementById('btn-share-questionnaire');
        if (activeQuestionnaireId) {
            btnShare.style.display = 'block';
            if (btnEditActiveQuest) btnEditActiveQuest.style.display = 'block';
        } else {
            btnShare.style.display = 'none';
            if (btnEditActiveQuest) btnEditActiveQuest.style.display = 'none';
        }
    });
    
    function renderQuestionsFields() {
        const quest = questionnaires.find(q => q.id === activeQuestionnaireId);
        if (!quest) return;
        
        dynamicQuestionsContainer.innerHTML = '';
        btnSubmitSaisie.disabled = false;
        
        const blocks = (quest.blocks || []).sort((a, b) => a.order_index - b.order_index);
        
        if (blocks.length === 0) {
            dynamicQuestionsContainer.innerHTML = '<p class="text-muted text-center py-4">Ce questionnaire ne contient aucun bloc. Cliquez sur "Éditer" pour en concevoir.</p>';
            return;
        }
        
        blocks.forEach(block => {
            const content = block.content || {};
            
            if (block.block_type === 'title') {
                const header = document.createElement('div');
                header.className = 'form-block-header text-center my-4';
                header.innerHTML = `
                    <h3 style="font-size: 16px; font-weight:800; margin-bottom:4px;">${content.title || quest.title}</h3>
                    <p class="text-muted" style="font-size: 12px; max-width:600px; margin:0 auto;">${content.description || ''}</p>
                `;
                dynamicQuestionsContainer.appendChild(header);
            }
            else if (block.block_type === 'section') {
                const section = document.createElement('div');
                section.className = 'form-block-section my-3';
                section.innerHTML = `
                    <h4 style="font-size: 13px; font-weight:700; color:var(--indigo); border-bottom:1px solid var(--border-color); padding-bottom:4px; text-transform:uppercase; letter-spacing:0.5px;">${content.title || 'Section'}</h4>
                `;
                dynamicQuestionsContainer.appendChild(section);
            }
            else if (block.block_type === 'text') {
                const text = document.createElement('div');
                text.className = 'form-block-text my-2 text-muted';
                text.innerHTML = `
                    <p style="font-size: 12.5px; line-height: 1.5; margin: 0;">${content.text || ''}</p>
                `;
                dynamicQuestionsContainer.appendChild(text);
            }
            else if (block.block_type === 'question') {
                const div = document.createElement('div');
                div.className = 'question-field-block my-3';
                
                let inputHtml = '';
                const qId = content.question_id || `block_${block.id}`;
                
                if (content.question_type === 'select') {
                    inputHtml = `<select name="q_${qId}" class="custom-select" ${content.is_required ? 'required' : ''}>`;
                    inputHtml += '<option value="" disabled selected>Sélectionner une option...</option>';
                    (content.choices || []).forEach(c => {
                        inputHtml += `<option value="${c}">${c}</option>`;
                    });
                    inputHtml += '</select>';
                } else {
                    inputHtml = `<textarea name="q_${qId}" rows="3" placeholder="${content.help_text || 'Écrire la réponse de la question...'}" ${content.is_required ? 'required' : ''}></textarea>`;
                }
                
                const reqStar = content.is_required ? '<span class="text-danger">*</span>' : '';
                
                div.innerHTML = `
                    <div class="form-group">
                        <label class="font-weight-bold" style="font-size:13px; display:block; margin-bottom:4px;">❓ ${content.label || 'Question'} ${reqStar}</label>
                        ${content.help_text ? `<small class="text-muted d-block mb-1" style="font-size:11px; margin-top:-2px;">${content.help_text}</small>` : ''}
                        ${inputHtml}
                    </div>
                `;
                dynamicQuestionsContainer.appendChild(div);
            }
            else {
                const div = document.createElement('div');
                div.className = 'question-field-block my-3';
                const qId = `block_${block.id}`;
                const label = content.label || block.block_type.toUpperCase();
                const icon = getBlockIcon(block.block_type);
                
                let inputHtml = '';
                if (block.block_type === 'comment') {
                    inputHtml = `<textarea name="q_${qId}" rows="3" placeholder="${content.help_text || 'Entrez vos commentaires...'}" ${content.is_required ? 'required' : ''}></textarea>`;
                } else if (block.block_type === 'checkbox') {
                    inputHtml = '<div class="checkbox-list-container d-flex flex-column gap-2 mt-2">';
                    (content.options || []).forEach((opt, oIdx) => {
                        inputHtml += `
                            <label class="d-flex align-items-center gap-2" style="font-weight:normal; font-size:12.5px; margin:0;">
                                <input type="checkbox" name="q_${qId}_opt_${oIdx}" value="${opt}">
                                <span>${opt}</span>
                            </label>
                        `;
                    });
                    inputHtml += '</div>';
                } else if (block.block_type === 'gps') {
                    inputHtml = `
                        <div class="d-flex gap-2 align-items-center mt-1">
                            <input type="text" name="q_${qId}" id="gps-input-${block.id}" class="form-control" style="font-size:13px; max-width: 250px;" placeholder="Latitude, Longitude" readonly ${content.is_required ? 'required' : ''}>
                            <button type="button" class="btn btn-secondary btn-sm" onclick="getCurrentGPSLocation(${block.id})">📍 Capturer GPS</button>
                        </div>
                    `;
                } else if (block.block_type === 'photo') {
                    inputHtml = `
                        <div class="photo-capture-wrapper mt-1">
                            <input type="file" name="q_${qId}" accept="image/*" capture="environment" class="form-control" style="font-size:12.5px; max-width: 350px;" ${content.is_required ? 'required' : ''}>
                        </div>
                    `;
                } else if (block.block_type === 'signature') {
                    inputHtml = `
                        <div class="signature-input-wrapper mt-1">
                            <input type="text" name="q_${qId}" class="form-control" placeholder="Écrivez votre nom pour signature..." style="font-size:13px; max-width: 350px;" ${content.is_required ? 'required' : ''}>
                        </div>
                    `;
                } else if (block.block_type === 'file') {
                    inputHtml = `
                        <div class="file-attachment-wrapper mt-1">
                            <input type="file" name="q_${qId}" class="form-control" style="font-size:12.5px; max-width: 350px;" ${content.is_required ? 'required' : ''}>
                        </div>
                    `;
                } else if (block.block_type === 'matrix') {
                    inputHtml = '<div class="matrix-input-table-wrapper overflow-auto mt-2">';
                    inputHtml += '<table class="table table-bordered table-sm" style="font-size:12px; background: rgba(255,255,255,0.02);"><thead><tr><th></th>';
                    (content.columns || []).forEach(col => {
                        inputHtml += `<th>${col}</th>`;
                    });
                    inputHtml += '</tr></thead><tbody>';
                    (content.rows || []).forEach((row, rIdx) => {
                        inputHtml += `<tr><td><strong>${row}</strong></td>`;
                        (content.columns || []).forEach((col, cIdx) => {
                            inputHtml += `<td><input type="radio" name="q_${qId}_row_${rIdx}" value="${col}"></td>`;
                        });
                        inputHtml += '</tr>';
                    });
                    inputHtml += '</tbody></table></div>';
                }
                
                const reqStar = content.is_required ? '<span class="text-danger">*</span>' : '';
                
                div.innerHTML = `
                    <div class="form-group">
                        <label class="font-weight-bold" style="font-size:13px; display:block; margin-bottom:4px;">${icon} ${label} ${reqStar}</label>
                        ${content.help_text ? `<small class="text-muted d-block mb-1" style="font-size:11px; margin-top:-2px;">${content.help_text}</small>` : ''}
                        ${inputHtml}
                    </div>
                `;
                dynamicQuestionsContainer.appendChild(div);
            }
        });
    }
    
    window.getCurrentGPSLocation = function(blockId) {
        if (!navigator.geolocation) {
            showToast("La géolocalisation n'est pas supportée par votre navigateur.", "error");
            return;
        }
        
        showToast("Recherche de la position GPS...", "info");
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude.toFixed(6);
                const lng = position.coords.longitude.toFixed(6);
                const input = document.getElementById(`gps-input-${blockId}`);
                if (input) {
                    input.value = `${lat}, ${lng}`;
                    showToast("Position GPS capturée avec succès !", "success");
                }
            },
            (error) => {
                showToast(`Erreur GPS : ${error.message}`, "error");
            },
            { enableHighAccuracy: true, timeout: 5000 }
        );
    };
    
    // Saisie formulaire d'entretien
    formInterviewSaisie.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const questionnaireId = parseInt(saisieQuestionnaireId.value);
        const title = document.getElementById('saisie-title').value;
        const interview_date = document.getElementById('saisie-date').value;
        const interviewer = document.getElementById('saisie-interviewer').value;
        const interviewee_name_or_group = document.getElementById('saisie-interviewee').value;
        const session_type = document.getElementById('saisie-type-session').value;
        const actor_category = document.getElementById('saisie-actor-category').value;
        
        const answers = {};
        const quest = questionnaires.find(q => q.id === questionnaireId);
        if (quest) {
            const blocks = quest.blocks || [];
            blocks.forEach(block => {
                const content = block.content || {};
                if (block.block_type === 'question') {
                    const qId = content.question_id || `block_${block.id}`;
                    const el = formInterviewSaisie.querySelector(`[name="q_${qId}"]`);
                    if (el) {
                        if (content.question_id) {
                            answers[content.question_id] = el.value;
                        } else {
                            answers[`block_${block.id}`] = el.value;
                        }
                    }
                } else {
                    const qId = `block_${block.id}`;
                    if (block.block_type === 'checkbox') {
                        const checked = [];
                        (content.options || []).forEach((opt, oIdx) => {
                            const checkbox = formInterviewSaisie.querySelector(`[name="q_${qId}_opt_${oIdx}"]`);
                            if (checkbox && checkbox.checked) {
                                checked.push(opt);
                            }
                        });
                        answers[qId] = checked.join(', ');
                    } else if (block.block_type === 'matrix') {
                        const matrixVals = [];
                        (content.rows || []).forEach((row, rIdx) => {
                            const radio = formInterviewSaisie.querySelector(`[name="q_${qId}_row_${rIdx}"]:checked`);
                            if (radio) {
                                matrixVals.push(`${row}: ${radio.value}`);
                            }
                        });
                        answers[qId] = matrixVals.join(' | ');
                    } else {
                        const el = formInterviewSaisie.querySelector(`[name="q_${qId}"]`);
                        if (el) {
                            answers[qId] = el.value;
                        }
                    }
                }
            });
        }
        
        const payload = {
            questionnaire_id: questionnaireId,
            title,
            interview_date,
            interviewer,
            interviewee_name_or_group,
            session_type,
            actor_category,
            answers
        };
        
        const isEdit = (editingSessionId !== null);
        const url = isEdit ? `/api/sessions/${editingSessionId}` : `/api/projects/${activeProjectId}/sessions`;
        const method = isEdit ? 'PUT' : 'POST';
        
        try {
            const result = await requestAPI(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (result.success) {
                showToast(isEdit ? "Entretien mis à jour avec succès !" : "Entretien enregistré avec succès !", "success");
                
                editingSessionId = null;
                formInterviewSaisie.reset();
                dynamicQuestionsContainer.innerHTML = '<p class="text-muted text-center py-4">Veuillez d\'abord sélectionner un questionnaire dans le panneau de gauche.</p>';
                btnSubmitSaisie.disabled = true;
                btnSubmitSaisie.innerText = "Enregistrer l'Entretien";
                btnSubmitSaisie.classList.remove('btn-warning');
                activeQuestionnaireId = null;
                selectQuestionnaire.value = "";
                
                const btnCancelEdit = document.getElementById('btn-cancel-edit-session');
                if (btnCancelEdit) btnCancelEdit.remove();
                document.querySelector('#tab-collecte h2').innerText = "Saisie Individuelle & Collective";
                
                const btnShare = document.getElementById('btn-share-questionnaire');
                if (btnShare) btnShare.style.display = 'none';
                if (btnEditActiveQuest) btnEditActiveQuest.style.display = 'none';
 
                switchTab('dashboard');
            }
        } catch (err) {
            console.error("Erreur lors de la sauvegarde de l'entretien:", err);
        }
    });    
    // --- MODAL CREATION DE QUESTIONNAIRE (CANVA/NOTION STYLE) ---
    const builderOverlay = document.getElementById('builder-overlay');
    const builderCanvas = document.getElementById('builder-canvas-area');
    const builderSavedBlocksContainer = document.getElementById('builder-saved-blocks-container');
    const propertiesPanelContent = document.getElementById('properties-panel-content');
    
    // Variables locales pour le builder
    let activeBuilderQuestionnaireId = null;
    let builderBlocks = [];
    let selectedBlockId = null;

    
    // Ouvrir la sélection de modèle
    btnCreateQuestionnaire.addEventListener('click', () => {
        if (!activeProjectId) {
            showToast("Veuillez d'abord sélectionner ou créer un projet actif (en haut à droite).", "warning");
            return;
        }
        document.getElementById('select-template-title').value = '';
        modalCreateQuestionnaireSelect.classList.add('active');
        
        // S'assurer que le premier modèle (Vide) est coché par défaut et actif visuellement
        const firstRadio = formSelectTemplateCreate.querySelector('input[name="template_cat"][value="vide"]');
        if (firstRadio) {
            firstRadio.checked = true;
            document.querySelectorAll('.template-option').forEach(opt => opt.classList.remove('active'));
            firstRadio.closest('.template-option').classList.add('active');
        }
    });
    
    // Fermer les modales de création
    document.getElementById('btn-close-select-template-modal').addEventListener('click', () => {
        modalCreateQuestionnaireSelect.classList.remove('active');
    });
    document.getElementById('btn-cancel-select-template').addEventListener('click', () => {
        modalCreateQuestionnaireSelect.classList.remove('active');
    });

    // Gérer la sélection visuelle des modèles
    document.querySelectorAll('.template-option').forEach(opt => {
        opt.addEventListener('click', () => {
            document.querySelectorAll('.template-option').forEach(o => o.classList.remove('active'));
            opt.classList.add('active');
            const radio = opt.querySelector('input[type="radio"]');
            if (radio) radio.checked = true;
        });
    });
    
    // Créer à partir d'un template
    formSelectTemplateCreate.addEventListener('submit', async (e) => {
        e.preventDefault();
        const title = document.getElementById('select-template-title').value;
        const template_id = formSelectTemplateCreate.querySelector('input[name="template_cat"]:checked').value;
        
        if (title && title.length > 255) {
            showToast("Le titre du questionnaire ne doit pas dépasser 255 caractères.", "warning");
            return;
        }
        
        try {
            const res = await requestAPI('/api/questionnaires/from-template', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project_id: activeProjectId,
                    template_id: template_id,
                    title: title
                })
            });
            if (res.success) {
                modalCreateQuestionnaireSelect.classList.remove('active');
                showToast("Questionnaire créé avec succès !", "success");
                loadQuestionnairesList();
                openVisualBuilder(res.questionnaire.id);
            }
        } catch (err) {
            console.error("Erreur de création à partir du modèle:", err);
        }
    });

    // Ouvrir le constructeur visuel
    async function openVisualBuilder(questionnaireId) {
        activeQuestionnaireId = questionnaireId; // Conserver actif après fermeture
        activeBuilderQuestionnaireId = questionnaireId;
        selectedBlockId = null;
        propertiesPanelContent.innerHTML = '<p class="text-muted text-center py-5">Sélectionnez un bloc sur le canvas pour modifier ses propriétés.</p>';
        
        try {
            const qDetails = questionnaires.find(q => q.id === questionnaireId) || {};
            document.getElementById('builder-questionnaire-title').innerText = qDetails.title || "Questionnaire";
            
            const activeProject = projects.find(p => p.id === activeProjectId) || {};
            document.getElementById('builder-project-name').innerText = activeProject.name || "Projet Actif";
            
            // Charger les blocs
            builderBlocks = await requestAPI(`/api/questionnaires/${questionnaireId}/blocks`);
            
            // Rendre le canvas
            renderCanvasBlocks();
            
            // Charger la bibliothèque de blocs personnalisés
            loadLibraryBlocks();
            
            // Ouvrir l'overlay
            builderOverlay.style.display = 'flex';
        } catch (err) {
            console.error("Erreur d'ouverture du constructeur:", err);
        }
    }
    
    if (btnEditActiveQuest) {
        btnEditActiveQuest.addEventListener('click', () => {
            if (activeQuestionnaireId) {
                openVisualBuilder(activeQuestionnaireId);
            }
        });
    }
    
    // Fermer le constructeur visuel
    document.getElementById('btn-builder-close').addEventListener('click', () => {
        builderOverlay.style.display = 'none';
        activeBuilderQuestionnaireId = null;
        loadQuestionnairesList();
    });

    // Rendre les blocs sur le Canvas
    function renderCanvasBlocks() {
        builderCanvas.innerHTML = '';
        const emptyState = document.getElementById('canvas-empty-state-msg');
        
        if (builderBlocks.length === 0) {
            if (emptyState) emptyState.style.display = 'flex';
            builderCanvas.appendChild(emptyState);
            document.getElementById('canvas-blocks-count').innerText = "0 blocs";
            document.getElementById('canvas-progress-fill').style.width = "0%";
            return;
        }
        
        if (emptyState) emptyState.style.display = 'none';
        
        // Trier par index
        builderBlocks.sort((a, b) => a.order_index - b.order_index);
        
        let questionsCount = 0;
        
        builderBlocks.forEach((block, idx) => {
            if (block.block_type === 'question') questionsCount++;
            
            const blockEl = document.createElement('div');
            blockEl.className = `builder-block ${selectedBlockId === block.id ? 'selected' : ''}`;
            blockEl.setAttribute('data-id', block.id);
            blockEl.setAttribute('draggable', 'true');
            
            let innerContentHtml = '';
            const content = block.content || {};
            
            if (block.block_type === 'title') {
                innerContentHtml = `
                    <div class="block-render-title">
                        <h2 style="font-size: 20px; font-weight:800; margin-bottom:4px;">${content.title || 'Titre du Questionnaire'}</h2>
                        <p class="text-muted" style="font-size:12px; margin:0;">${content.description || 'Description / objectifs...'}</p>
                    </div>
                `;
            } else if (block.block_type === 'section') {
                innerContentHtml = `
                    <div class="block-render-section">
                        <h3 style="font-size: 15px; font-weight:700; margin:0;">${content.title || 'Section sans titre'}</h3>
                    </div>
                `;
            } else if (block.block_type === 'text') {
                innerContentHtml = `
                    <div class="block-render-text">
                        <p style="font-size: 13px; margin:0; opacity:0.85;">${content.text || 'Entrez votre texte descriptif ici...'}</p>
                    </div>
                `;
            } else if (block.block_type === 'question') {
                const isReqStar = content.is_required ? '<span class="text-danger">*</span>' : '';
                const qTypeLabel = content.question_type === 'select' ? 'Choix unique' : 'Texte libre';
                innerContentHtml = `
                    <div class="block-render-question">
                        <label class="font-weight-bold" style="font-size:13.5px; display:block;">❓ ${content.label || 'Question sans titre'} ${isReqStar}</label>
                        <div class="text-muted" style="font-size: 11px; margin-top: 2px;">Type : ${qTypeLabel} ${content.help_text ? `| Aide : ${content.help_text}` : ''}</div>
                        ${content.question_type === 'select' ? 
                            `<select class="custom-select mt-2" style="font-size:12.5px;" disabled><option>${(content.choices || []).join(', ') || 'Aucun choix défini'}</option></select>` : 
                            `<textarea class="form-control mt-2" style="font-size:12.5px;" rows="2" placeholder="Zone de saisie libre..." disabled></textarea>`
                        }
                    </div>
                `;
            } else {
                const label = content.label || block.block_type.toUpperCase();
                const icon = getBlockIcon(block.block_type);
                innerContentHtml = `
                    <div class="block-render-generic">
                        <div class="d-flex align-items-center gap-2">
                            <span>${icon}</span>
                            <span class="font-weight-bold" style="font-size:13.5px;">${label}</span>
                        </div>
                        <p class="text-muted small mt-1 mb-0" style="font-size:11px;">${content.help_text || 'Composant automatique de saisie terrain.'}</p>
                    </div>
                `;
            }
            
            blockEl.innerHTML = `
                <div class="block-controls">
                    <button class="btn-block-action btn-duplicate-block" title="Dupliquer">👯</button>
                    <button class="btn-block-action btn-save-lib" title="Sauvegarder dans bibliothèque">💾</button>
                    <button class="btn-block-action btn-delete-block" title="Supprimer">🗑️</button>
                </div>
                ${innerContentHtml}
            `;
            
            blockEl.addEventListener('click', (e) => {
                if (e.target.closest('.block-controls')) return;
                selectCanvasBlock(block.id);
            });
            
            blockEl.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('text/plain', JSON.stringify({ source: 'canvas', id: block.id }));
                blockEl.classList.add('dragging');
            });
            
            blockEl.addEventListener('dragend', () => {
                blockEl.classList.remove('dragging');
            });
            
            blockEl.addEventListener('dragover', (e) => {
                e.preventDefault();
                blockEl.classList.add('drag-over');
            });
            
            blockEl.addEventListener('dragleave', () => {
                blockEl.classList.remove('drag-over');
            });
            
            blockEl.addEventListener('drop', async (e) => {
                e.preventDefault();
                blockEl.classList.remove('drag-over');
                const data = JSON.parse(e.dataTransfer.getData('text/plain'));
                
                if (data.source === 'canvas') {
                    const draggedId = data.id;
                    if (draggedId === block.id) return;
                    
                    const draggedIdx = builderBlocks.findIndex(b => b.id === draggedId);
                    const targetIdx = builderBlocks.findIndex(b => b.id === block.id);
                    
                    const [draggedBlock] = builderBlocks.splice(draggedIdx, 1);
                    builderBlocks.splice(targetIdx, 0, draggedBlock);
                    
                    builderBlocks.forEach((b, i) => b.order_index = i + 1);
                    renderCanvasBlocks();
                    
                    await requestAPI(`/api/questionnaires/${activeBuilderQuestionnaireId}/blocks/reorder`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ blocks: builderBlocks.map(b => ({ id: b.id, order_index: b.order_index })) })
                    });
                } else if (data.source === 'library') {
                    const newType = data.type;
                    const qType = data.qtype;
                    const contentDefault = data.content || getBlockDefaultContent(newType, qType);
                    
                    const targetIdx = builderBlocks.findIndex(b => b.id === block.id);
                    
                    try {
                        const res = await requestAPI(`/api/questionnaires/${activeBuilderQuestionnaireId}/blocks`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                block_type: newType,
                                content: contentDefault,
                                order_index: targetIdx + 1
                            })
                        });
                        if (res.success) {
                            builderBlocks.splice(targetIdx + 1, 0, res.block);
                            builderBlocks.forEach((b, i) => b.order_index = i + 1);
                            renderCanvasBlocks();
                            selectCanvasBlock(res.block.id);
                        }
                    } catch (err) {
                        console.error("Erreur drop de bibliothèque:", err);
                    }
                }
            });
            
            blockEl.querySelector('.btn-duplicate-block').addEventListener('click', () => duplicateBlock(block));
            blockEl.querySelector('.btn-save-lib').addEventListener('click', () => saveBlockToLibrary(block));
            blockEl.querySelector('.btn-delete-block').addEventListener('click', () => deleteCanvasBlock(block.id));
            
            builderCanvas.appendChild(blockEl);
        });
        
        document.getElementById('canvas-blocks-count').innerText = `${builderBlocks.length} bloc(s)`;
        const progressPct = builderBlocks.length > 0 ? Math.min(100, (questionsCount / builderBlocks.length) * 100) : 0;
        document.getElementById('canvas-progress-fill').style.width = `${progressPct}%`;
    }
    
    function selectCanvasBlock(blockId) {
        selectedBlockId = blockId;
        
        const blockEls = builderCanvas.querySelectorAll('.builder-block');
        blockEls.forEach(el => {
            if (parseInt(el.getAttribute('data-id')) === blockId) {
                el.classList.add('selected');
            } else {
                el.classList.remove('selected');
            }
        });
        
        const block = builderBlocks.find(b => b.id === blockId);
        if (!block) return;
        
        renderPropertiesPanel(block);
        
        // Auto-focus le champ d'édition principal dans le panneau de propriétés pour "donner la main" directement
        setTimeout(() => {
            const primaryInput = document.getElementById('prop-q-label') || 
                                 document.getElementById('prop-section-title') || 
                                 document.getElementById('prop-text-content') || 
                                 document.getElementById('prop-title-text') || 
                                 document.getElementById('prop-generic-label');
            if (primaryInput) {
                primaryInput.focus();
                // Sélectionner tout le texte pour faciliter le remplacement rapide
                primaryInput.select();
            }
        }, 50);
    }
    
    function renderPropertiesPanel(block) {
        const content = block.content || {};
        propertiesPanelContent.innerHTML = '';
        
        let fieldsHtml = '';
        
        if (block.block_type === 'title') {
            fieldsHtml = `
                <div class="property-group">
                    <label>Titre principal</label>
                    <input type="text" id="prop-title-text" class="form-control" value="${content.title || ''}">
                </div>
                <div class="property-group">
                    <label>Description du Questionnaire</label>
                    <textarea id="prop-desc-text" class="form-control" rows="3">${content.description || ''}</textarea>
                </div>
            `;
        } else if (block.block_type === 'section') {
            fieldsHtml = `
                <div class="property-group">
                    <label>Titre de la Section</label>
                    <input type="text" id="prop-section-title" class="form-control" value="${content.title || ''}">
                </div>
            `;
        } else if (block.block_type === 'text') {
            fieldsHtml = `
                <div class="property-group">
                    <label>Texte explicatif</label>
                    <textarea id="prop-text-content" class="form-control" rows="4">${content.text || ''}</textarea>
                </div>
            `;
        } else if (block.block_type === 'question') {
            const isTextSelected = content.question_type === 'text' ? 'selected' : '';
            const isSelectSelected = content.question_type === 'select' ? 'selected' : '';
            const choicesStr = (content.choices || []).join(', ');
            
            fieldsHtml = `
                <div class="property-group">
                    <label>Libellé de la Question</label>
                    <input type="text" id="prop-q-label" class="form-control" value="${content.label || ''}">
                </div>
                <div class="property-group">
                    <label>Type de Réponse</label>
                    <select id="prop-q-type" class="custom-select">
                        <option value="text" ${isTextSelected}>Texte libre</option>
                        <option value="select" ${isSelectSelected}>Choix unique</option>
                    </select>
                </div>
                <div class="property-group" id="prop-choices-wrapper" style="display: ${content.question_type === 'select' ? 'block' : 'none'};">
                    <label>Choix (séparés par des virgules)</label>
                    <input type="text" id="prop-q-choices" class="form-control" value="${choicesStr}">
                </div>
                <div class="property-group">
                    <label>Aide à la saisie</label>
                    <input type="text" id="prop-q-help" class="form-control" value="${content.help_text || ''}">
                </div>
                <div class="form-check mb-3">
                    <input type="checkbox" id="prop-q-required" class="form-check-input" ${content.is_required ? 'checked' : ''}>
                    <label class="form-check-label" for="prop-q-required">Obligatoire</label>
                </div>
            `;
        } else {
            fieldsHtml = `
                <div class="property-group">
                    <label>Libellé du champ</label>
                    <input type="text" id="prop-generic-label" class="form-control" value="${content.label || block.block_type.toUpperCase()}">
                </div>
                <div class="property-group">
                    <label>Instructions / aide</label>
                    <input type="text" id="prop-generic-help" class="form-control" value="${content.help_text || ''}">
                </div>
            `;
        }
        
        propertiesPanelContent.innerHTML = fieldsHtml;
        
        const bindInput = (id, propPath, valueGetter) => {
            const el = document.getElementById(id);
            if (!el) return;
            
            const handler = async () => {
                const val = valueGetter(el);
                const blockContent = block.content || {};
                blockContent[propPath] = val;
                block.content = blockContent;
                
                renderCanvasBlocks();
                
                await requestAPI(`/api/blocks/${block.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: blockContent })
                });
            };
            
            el.addEventListener('input', debounce(handler, 400));
            el.addEventListener('change', handler);
        };
        
        if (block.block_type === 'title') {
            bindInput('prop-title-text', 'title', el => el.value);
            bindInput('prop-desc-text', 'description', el => el.value);
        } else if (block.block_type === 'section') {
            bindInput('prop-section-title', 'title', el => el.value);
        } else if (block.block_type === 'text') {
            bindInput('prop-text-content', 'text', el => el.value);
        } else if (block.block_type === 'question') {
            bindInput('prop-q-label', 'label', el => el.value);
            bindInput('prop-q-help', 'help_text', el => el.value);
            bindInput('prop-q-required', 'is_required', el => el.checked);
            
            const qTypeEl = document.getElementById('prop-q-type');
            if (qTypeEl) {
                qTypeEl.addEventListener('change', async (e) => {
                    const type = e.target.value;
                    const wrapper = document.getElementById('prop-choices-wrapper');
                    wrapper.style.display = type === 'select' ? 'block' : 'none';
                    
                    block.content.question_type = type;
                    renderCanvasBlocks();
                    
                    await requestAPI(`/api/blocks/${block.id}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ content: block.content })
                    });
                });
            }
            
            const choicesEl = document.getElementById('prop-q-choices');
            if (choicesEl) {
                choicesEl.addEventListener('input', debounce(async () => {
                    const list = choicesEl.value.split(',').map(s => s.trim()).filter(s => s.length > 0);
                    block.content.choices = list;
                    renderCanvasBlocks();
                    
                    await requestAPI(`/api/blocks/${block.id}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ content: block.content })
                    });
                }, 400));
            }
        } else {
            bindInput('prop-generic-label', 'label', el => el.value);
            bindInput('prop-generic-help', 'help_text', el => el.value);
        }
    }
    
    function debounce(func, wait) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    async function duplicateBlock(block) {
        try {
            const res = await requestAPI(`/api/questionnaires/${activeBuilderQuestionnaireId}/blocks`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    block_type: block.block_type,
                    content: JSON.parse(JSON.stringify(block.content)),
                    order_index: block.order_index + 1
                })
            });
            if (res.success) {
                const insertIdx = builderBlocks.findIndex(b => b.id === block.id);
                builderBlocks.splice(insertIdx + 1, 0, res.block);
                builderBlocks.forEach((b, i) => b.order_index = i + 1);
                renderCanvasBlocks();
                selectCanvasBlock(res.block.id);
                showToast("Bloc dupliqué !", "success");
            }
        } catch (err) {
            console.error("Erreur duplication bloc:", err);
        }
    }

    async function deleteCanvasBlock(blockId) {
        openConfirmModal("ce bloc", "Voulez-vous vraiment supprimer ce bloc du questionnaire ?", async () => {
            try {
                const res = await requestAPI(`/api/blocks/${blockId}`, { method: 'DELETE' });
                if (res.success) {
                    builderBlocks = builderBlocks.filter(b => b.id !== blockId);
                    builderBlocks.forEach((b, i) => b.order_index = i + 1);
                    renderCanvasBlocks();
                    if (selectedBlockId === blockId) {
                        selectedBlockId = null;
                        propertiesPanelContent.innerHTML = '<p class="text-muted text-center py-5">Sélectionnez un bloc sur le canvas pour modifier ses propriétés.</p>';
                    }
                    showToast("Bloc supprimé avec succès !", "success");
                }
            } catch (err) {
                console.error("Erreur suppression bloc:", err);
            }
        });
    }
    
    async function saveBlockToLibrary(block) {
        const name = prompt("Nom de ce modèle de bloc dans votre bibliothèque :", block.content.label || block.content.title || block.block_type);
        if (!name) return;
        
        try {
            const res = await requestAPI('/api/library', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    block_type: block.block_type,
                    name: name,
                    content: block.content,
                    is_shared: false
                })
            });
            if (res.success) {
                showToast("Bloc sauvegardé dans votre bibliothèque !", "success");
                loadLibraryBlocks();
            }
        } catch (err) {
            console.error("Erreur sauvegarde bibliothèque:", err);
        }
    }
    
    async function loadLibraryBlocks() {
        try {
            const libBlocks = await requestAPI('/api/library');
            builderSavedBlocksContainer.innerHTML = '';
            
            if (libBlocks.length === 0) {
                builderSavedBlocksContainer.innerHTML = '<p class="text-muted text-center py-2" style="font-size: 11px;">Aucun bloc personnalisé.</p>';
                return;
            }
            
            libBlocks.forEach(lb => {
                const div = document.createElement('div');
                div.className = 'draggable-block-item';
                div.setAttribute('draggable', 'true');
                div.innerHTML = `
                    <span>📦 ${lb.name}</span>
                    <button class="btn-delete-lib-item" style="background:none; border:none; color:var(--text-muted); cursor:pointer; font-size:11px;">🗑️</button>
                `;
                
                div.addEventListener('dragstart', (e) => {
                    e.dataTransfer.setData('text/plain', JSON.stringify({ source: 'library', type: lb.block_type, qtype: lb.content.question_type, content: lb.content }));
                });
                
                div.addEventListener('click', async (e) => {
                    if (e.target.closest('.btn-delete-lib-item')) return;
                    
                    try {
                        const nextIdx = builderBlocks.length + 1;
                        const res = await requestAPI(`/api/questionnaires/${activeBuilderQuestionnaireId}/blocks`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                block_type: lb.block_type,
                                content: lb.content,
                                order_index: nextIdx
                            })
                        });
                        if (res.success) {
                            builderBlocks.push(res.block);
                            renderCanvasBlocks();
                            selectCanvasBlock(res.block.id);
                            showToast("Bloc personnalisé inséré !", "success");
                        }
                    } catch (err) {
                        console.error("Erreur insertion bloc bibliothèque:", err);
                    }
                });
                
                div.querySelector('.btn-delete-lib-item').addEventListener('click', async () => {
                    if (confirm("Supprimer ce modèle de bloc de votre bibliothèque ?")) {
                        try {
                            const res = await requestAPI(`/api/library/${lb.id}`, { method: 'DELETE' });
                            if (res.success) {
                                showToast("Bloc retiré de la bibliothèque.", "success");
                                loadLibraryBlocks();
                            }
                        } catch (err) {
                            console.error("Erreur suppression bibliothèque:", err);
                        }
                    }
                });
                
                builderSavedBlocksContainer.appendChild(div);
            });
        } catch (err) {
            console.error("Erreur chargement bibliothèque:", err);
        }
    }

    const draggableItems = document.querySelectorAll('.builder-sidebar-left .draggable-block-item');
    draggableItems.forEach(item => {
        item.addEventListener('dragstart', (e) => {
            const type = item.getAttribute('data-type');
            const qtype = item.getAttribute('data-qtype');
            e.dataTransfer.setData('text/plain', JSON.stringify({ source: 'library', type, qtype }));
        });
        
        item.addEventListener('click', async () => {
            if (!activeBuilderQuestionnaireId) return;
            const type = item.getAttribute('data-type');
            const qtype = item.getAttribute('data-qtype');
            const content = getBlockDefaultContent(type, qtype);
            const nextIdx = builderBlocks.length + 1;
            
            try {
                const res = await requestAPI(`/api/questionnaires/${activeBuilderQuestionnaireId}/blocks`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        block_type: type,
                        content: content,
                        order_index: nextIdx
                    })
                });
                if (res.success) {
                    builderBlocks.push(res.block);
                    renderCanvasBlocks();
                    selectCanvasBlock(res.block.id);
                    builderCanvas.scrollTop = builderCanvas.scrollHeight;
                }
            } catch (err) {
                console.error("Erreur ajout bloc par clic:", err);
            }
        });
    });
    
    builderCanvas.addEventListener('dragover', (e) => {
        e.preventDefault();
    });
    
    builderCanvas.addEventListener('drop', async (e) => {
        e.preventDefault();
        if (e.target.closest('.builder-block')) return;
        
        const data = JSON.parse(e.dataTransfer.getData('text/plain'));
        if (data.source === 'library') {
            const content = data.content || getBlockDefaultContent(data.type, data.qtype);
            const nextIdx = builderBlocks.length + 1;
            
            try {
                const res = await requestAPI(`/api/questionnaires/${activeBuilderQuestionnaireId}/blocks`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        block_type: data.type,
                        content: content,
                        order_index: nextIdx
                    })
                });
                if (res.success) {
                    builderBlocks.push(res.block);
                    renderCanvasBlocks();
                    selectCanvasBlock(res.block.id);
                }
            } catch (err) {
                console.error("Erreur drop canvas vide:", err);
            }
        }
    });

    document.getElementById('btn-canvas-add-block-bottom').addEventListener('click', async () => {
        if (!activeBuilderQuestionnaireId) return;
        const nextIdx = builderBlocks.length + 1;
        
        try {
            const res = await requestAPI(`/api/questionnaires/${activeBuilderQuestionnaireId}/blocks`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    block_type: 'question',
                    content: getBlockDefaultContent('question', 'text'),
                    order_index: nextIdx
                })
            });
            if (res.success) {
                builderBlocks.push(res.block);
                renderCanvasBlocks();
                selectCanvasBlock(res.block.id);
            }
        } catch (err) {
            console.error("Erreur ajout bas du canvas:", err);
        }
    });

    document.getElementById('btn-builder-save').addEventListener('click', () => {
        if (document.activeElement) {
            document.activeElement.blur();
        }
        showToast("Toutes les modifications ont été enregistrées avec succès !", "success");
    });
    
    document.getElementById('btn-builder-preview').addEventListener('click', () => {
        builderOverlay.style.display = 'none';
        activeQuestionnaireId = activeBuilderQuestionnaireId;
        selectQuestionnaire.value = activeQuestionnaireId;
        renderQuestionsFields();
        switchTab('collecte');
    });

    function getBlockDefaultContent(type, qtype) {
        if (type === 'section') return { title: 'Nouvelle Section' };
        if (type === 'text') return { text: 'Nouveau paragraphe descriptif...' };
        if (type === 'question') {
            if (qtype === 'select') {
                return { label: 'Nouvelle Question à choix', question_type: 'select', choices: ['Option A', 'Option B'], is_required: false, help_text: '' };
            }
            return { label: 'Nouvelle Question textuelle', question_type: 'text', is_required: false, help_text: '' };
        }
        if (type === 'checkbox') return { label: 'Liste de contrôle', options: ['Tâche 1', 'Tâche 2'] };
        if (type === 'matrix') return { label: 'Grille d\'évaluation', rows: ['Ligne 1'], columns: ['Colonne 1'] };
        return { label: `Champ ${type.toUpperCase()}`, help_text: '' };
    }
    
    function getBlockIcon(type) {
        const icons = {
            signature: '✍️',
            gps: '📍',
            photo: '📷',
            file: '📁',
            comment: '💬',
            checkbox: '☑️',
            matrix: '📊'
        };
        return icons[type] || '❓';
    }

    // --- ASSISTANT IA CRÉATION ---
    const btnTriggerAiBuilder = document.getElementById('btn-trigger-ai-builder');
    
    btnTriggerAiBuilder.addEventListener('click', () => {
        document.getElementById('ai-quest-prompt-input').value = '';
        modalAiAssistantQuest.classList.add('active');
    });
    
    document.getElementById('btn-close-ai-quest-modal').addEventListener('click', () => modalAiAssistantQuest.classList.remove('active'));
    document.getElementById('btn-cancel-ai-quest').addEventListener('click', () => modalAiAssistantQuest.classList.remove('active'));
    
    document.getElementById('btn-submit-ai-quest').addEventListener('click', async () => {
        const prompt = document.getElementById('ai-quest-prompt-input').value;
        if (!prompt) return;
        
        const loader = document.getElementById('ai-quest-loader');
        loader.style.display = 'block';
        
        try {
            const res = await requestAPI('/api/assistant/create-questionnaire', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: prompt })
            });
            if (res.success) {
                const confirmRes = await requestAPI('/api/questionnaires/import/confirm', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        project_id: activeProjectId,
                        structure: res.structure
                    })
                });
                if (confirmRes.success) {
                    modalAiAssistantQuest.classList.remove('active');
                    showToast("Questionnaire généré par l'IA avec succès !", "success");
                    loadQuestionnairesList();
                    openVisualBuilder(confirmRes.questionnaire.id);
                }
            }
        } catch (err) {
            console.error("Erreur de génération IA:", err);
        } finally {
            loader.style.display = 'none';
        }
    });

    // --- IMPORTS DE FICHIERS QUESTIONNAIRE (IA) ---
    const btnTriggerImportBuilder = document.getElementById('btn-trigger-import-builder');
    const importFileDropArea = document.getElementById('import-file-drop-area');
    const importFileInput = document.getElementById('import-file-input');
    const btnConfirmImportQuest = document.getElementById('btn-confirm-import-quest');
    
    let importedStructure = null;
    
    btnTriggerImportBuilder.addEventListener('click', () => {
        importedStructure = null;
        btnConfirmImportQuest.disabled = true;
        document.getElementById('import-preview-results').style.display = 'none';
        document.getElementById('import-file-label').innerHTML = 'Glissez-déposez votre document ici ou <span class="file-browse-btn">parcourez</span>';
        modalImportQuestionnaire.classList.add('active');
    });
    
    document.getElementById('btn-close-import-modal').addEventListener('click', () => modalImportQuestionnaire.classList.remove('active'));
    document.getElementById('btn-cancel-import-quest').addEventListener('click', () => modalImportQuestionnaire.classList.remove('active'));
    
    importFileInput.addEventListener('click', (e) => e.stopPropagation());
    
    importFileDropArea.addEventListener('click', (e) => {
        if (e.target === importFileInput) return;
        importFileInput.click();
    });
    
    importFileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) handleImportFile(e.target.files[0]);
    });
    
    importFileDropArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        importFileDropArea.style.borderColor = 'var(--indigo)';
    });
    
    importFileDropArea.addEventListener('dragleave', () => {
        importFileDropArea.style.borderColor = 'rgba(255,255,255,0.1)';
    });
    
    importFileDropArea.addEventListener('drop', (e) => {
        e.preventDefault();
        importFileDropArea.style.borderColor = 'rgba(255,255,255,0.1)';
        if (e.dataTransfer.files.length > 0) handleImportFile(e.dataTransfer.files[0]);
    });
    
    async function handleImportFile(file) {
        console.log("handleImportFile appelé pour :", file.name, "Taille:", file.size);
        document.getElementById('import-file-label').innerText = `Fichier sélectionné : ${file.name}`;
        
        const loader = document.getElementById('import-analysis-loader');
        loader.style.display = 'block';
        document.getElementById('import-preview-results').style.display = 'none';
        btnConfirmImportQuest.disabled = true;
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const res = await requestAPI('/api/questionnaires/import', {
                method: 'POST',
                body: formData
            });
            console.log("Réponse de l'API d'import :", res);
            
            if (res && res.success) {
                importedStructure = res.structure;
                
                const previewBox = document.getElementById('import-preview-box-content');
                previewBox.innerHTML = `
                    <strong>${importedStructure.title}</strong><br>
                    <small>${importedStructure.description || 'Pas de description'}</small>
                    <ul class="mt-2 pl-3" style="text-align: left;">
                        ${(importedStructure.blocks || []).map(b => `<li>${b.block_type.toUpperCase()} : ${b.content.label || b.content.title || 'Champ'}</li>`).join('')}
                    </ul>
                `;
                document.getElementById('import-preview-results').style.display = 'block';
                btnConfirmImportQuest.disabled = false;
                showToast("Fichier analysé avec succès !", "success");
            } else {
                showToast(res.message || "Erreur de traitement lors de l'analyse du fichier.", "error");
            }
        } catch (err) {
            console.error("Erreur lors de l'import:", err);
            showToast(`Impossible d'importer le fichier : ${err.message}`, "error");
        } finally {
            loader.style.display = 'none';
        }
    }
    
    btnConfirmImportQuest.addEventListener('click', async () => {
        if (!importedStructure) return;
        
        try {
            const res = await requestAPI('/api/questionnaires/import/confirm', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    project_id: activeProjectId,
                    structure: importedStructure
                })
            });
            if (res.success) {
                modalImportQuestionnaire.classList.remove('active');
                showToast("Questionnaire importé avec succès !", "success");
                loadQuestionnairesList();
                openVisualBuilder(res.questionnaire.id);
            }
        } catch (err) {
            console.error("Erreur de confirmation de l'import:", err);
        }
    });

    // --- LIENS EXPORT DANS LE BUILDER ---
    document.getElementById('export-word-link').addEventListener('click', (e) => {
        e.preventDefault();
        window.open(`/api/questionnaires/${activeBuilderQuestionnaireId}/export/word`, '_blank');
    });
    
    document.getElementById('export-excel-link').addEventListener('click', (e) => {
        e.preventDefault();
        window.open(`/api/questionnaires/${activeBuilderQuestionnaireId}/export/excel`, '_blank');
    });
    
    document.getElementById('export-pdf-link').addEventListener('click', (e) => {
        e.preventDefault();
        window.open(`/api/questionnaires/${activeBuilderQuestionnaireId}/export/pdf`, '_blank');
    });
    
    document.getElementById('export-mobile-link').addEventListener('click', (e) => {
        e.preventDefault();
        window.open(`/api/questionnaires/${activeBuilderQuestionnaireId}/export/mobile`, '_blank');
    });

    // --- 8. ANGLAIS ANALYSE TRIANGULATION & MATRICE ---
    const selectCompareQuestion = document.getElementById('compare-question-select');
    const matrixContainer = document.getElementById('triangulation-matrix-cards');
    let analysisDataGlobal = null;
    
    async function loadTriangulationData() {
        if (!activeProjectId) {
            document.getElementById('ai-gauge-sentiment-label').innerText = "-";
            document.getElementById('ai-gauge-sentiment-label').style.borderColor = "var(--border-color)";
            document.getElementById('ai-gauge-sentiment-label').style.boxShadow = "none";
            document.getElementById('ai-metric-score-value').innerText = "Veuillez d'abord créer un projet.";
            document.getElementById('ai-themes-list').innerHTML = "<p class='text-muted'>Aucune donnée.</p>";
            document.getElementById('ai-recommendations-list').innerHTML = "<p class='text-muted'>Aucune recommandation.</p>";
            selectCompareQuestion.innerHTML = '<option value="" disabled selected>Aucun projet...</option>';
            matrixContainer.innerHTML = '<div class="text-center text-muted py-5"><p>Veuillez d\'abord créer un projet.</p></div>';
            return;
        }
        
        try {
            const data = await requestAPI(`/api/projects/${activeProjectId}/triangulation`, { silent: true });
            analysisDataGlobal = data;
            
            if (!data.success) {
                document.getElementById('ai-gauge-sentiment-label').innerText = "-";
                document.getElementById('ai-gauge-sentiment-label').style.borderColor = "var(--border-color)";
                document.getElementById('ai-gauge-sentiment-label').style.boxShadow = "none";
                document.getElementById('ai-metric-score-value').innerText = "Pas d'entretien enregistré.";
                document.getElementById('ai-themes-list').innerHTML = "<p class='text-muted'>Aucune donnée.</p>";
                document.getElementById('ai-recommendations-list').innerHTML = "<p class='text-muted'>Aucune recommandation.</p>";
                selectCompareQuestion.innerHTML = '<option value="" disabled selected>Aucune question...</option>';
                matrixContainer.innerHTML = '<div class="text-center text-muted py-5"><p>Veuillez d\'abord enregistrer des entretiens.</p></div>';
                return;
            }
            
            const score = data.avg_sentiment_score;
            const label = data.sentiment_label;
            
            const gauge = document.getElementById('ai-gauge-sentiment-label');
            gauge.innerText = label;
            document.getElementById('ai-metric-score-value').innerText = `Score de sentiment: ${score} / 1.0`;
            
            if (score > 0.15) {
                gauge.style.borderColor = 'var(--success)';
                gauge.style.boxShadow = '0 0 15px rgba(16, 185, 129, 0.4)';
                gauge.style.color = 'var(--success)';
            } else if (score < -0.15) {
                gauge.style.borderColor = 'var(--danger)';
                gauge.style.boxShadow = '0 0 15px rgba(239, 68, 68, 0.4)';
                gauge.style.color = 'var(--danger)';
            } else {
                gauge.style.borderColor = 'var(--warning)';
                gauge.style.boxShadow = '0 0 15px rgba(245, 158, 11, 0.4)';
                gauge.style.color = 'var(--warning)';
            }
            
            const themesDiv = document.getElementById('ai-themes-list');
            themesDiv.innerHTML = '';
            
            const maxWeight = data.themes.length > 0 ? Math.max(...data.themes.map(t => t.weight)) : 1;
            
            data.themes.forEach(t => {
                const percent = Math.round((t.weight / maxWeight) * 100);
                const row = document.createElement('div');
                row.className = 'ai-theme-row';
                row.innerHTML = `
                    <div class="ai-theme-meta">
                        <span>${t.theme}</span>
                        <strong>Poids : ${t.weight}</strong>
                    </div>
                    <div class="ai-theme-bar-bg">
                        <div class="ai-theme-bar-fill" style="width: ${percent}%;"></div>
                    </div>
                `;
                themesDiv.appendChild(row);
            });
            
            const recDiv = document.getElementById('ai-recommendations-list');
            recDiv.innerHTML = '';
            
            data.recommendations.forEach(rec => {
                const card = document.createElement('div');
                card.className = `ai-rec-card priority-${rec.priority}`;
                card.innerHTML = `
                    <h4>${rec.title}</h4>
                    <p>${rec.description}</p>
                `;
                recDiv.appendChild(card);
            });
            
            loadCompareQuestions();
        } catch (err) {
            console.error("Erreur de chargement triangulation:", err);
        }
    }
    
    async function loadCompareQuestions() {
        if (!activeProjectId) return;
        
        try {
            const quests = await requestAPI(`/api/projects/${activeProjectId}/questionnaires`);
            if (quests.length === 0) {
                selectCompareQuestion.innerHTML = '<option value="" disabled selected>Aucun questionnaire...</option>';
                return;
            }
            
            const firstQuest = quests[0];
            selectCompareQuestion.innerHTML = '';
            
            firstQuest.questions.forEach(q => {
                const opt = document.createElement('option');
                opt.value = q.id;
                opt.innerText = `${q.order_num}. ${q.text.substring(0, 50)}...`;
                selectCompareQuestion.appendChild(opt);
            });
            
            if (firstQuest.questions.length > 0) {
                renderTriangulationMatrix(firstQuest.questions[0].id);
            }
        } catch (err) {
            console.error("Erreur de chargement des questions à comparer:", err);
        }
    }
    
    selectCompareQuestion.addEventListener('change', (e) => {
        renderTriangulationMatrix(parseInt(e.target.value));
    });
    
    async function renderTriangulationMatrix(questionId) {
        if (!activeProjectId) return;
        
        try {
            const sessions = await requestAPI(`/api/projects/${activeProjectId}/sessions`);
            
            const actorAnswers = {
                'Bénéficiaire': [],
                'Partenaire': [],
                'Équipe Projet': [],
                'Autorité Locale': []
            };
            
            sessions.forEach(s => {
                const ans = s.answers.find(a => a.question_id === questionId);
                if (ans && ans.answer_text) {
                    actorAnswers[s.actor_category].push({
                        text: ans.answer_text,
                        sessionTitle: s.title,
                        interviewee: s.interviewee_name_or_group
                    });
                }
            });
            
            matrixContainer.innerHTML = '';
            let hasAnswers = false;
            
            Object.keys(actorAnswers).forEach(actor => {
                const answers = actorAnswers[actor];
                if (answers.length === 0) return;
                
                hasAnswers = true;
                
                const actorCard = document.createElement('div');
                actorCard.className = 'triangulation-actor-card';
                
                let answersHtml = '';
                answers.forEach(a => {
                    answersHtml += `
                        <div class="matrix-answer-item">
                            "${a.text}"
                            <div class="matrix-answer-meta">
                                <span>🗣️ ${a.interviewee}</span>
                                <span>📋 ${a.sessionTitle}</span>
                            </div>
                        </div>
                    `;
                });
                
                actorCard.innerHTML = `
                    <div class="triangulation-actor-header">
                        <span class="actor-name">${actor}</span>
                        <span class="badge badge-info">${answers.length} réponse(s)</span>
                    </div>
                    <div class="triangulation-actor-answers">
                        ${answersHtml}
                    </div>
                `;
                matrixContainer.appendChild(actorCard);
            });
            
            if (!hasAnswers) {
                matrixContainer.innerHTML = '<div class="text-center text-muted py-5"><p>Aucune réponse recueillie pour cette question spécifique.</p></div>';
            }
        } catch (err) {
            console.error("Erreur de rendu matriciel:", err);
        }
    }

    // --- 9. CHAT ASSISTANT IA ---
    const chatInput = document.getElementById('chat-input-field');
    const btnSendChat = document.getElementById('btn-send-message');
    const messagesArea = document.getElementById('chat-messages-area');
    const btnClearChat = document.getElementById('btn-clear-chat');
    
    function appendMessage(text, isOutgoing) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isOutgoing ? 'outgoing' : 'incoming'}`;
        
        let formattedText = text;
        if (!isOutgoing) {
            formattedText = formattedText.replace(/### (.*?)\n/g, '<h4>$1</h4>');
            formattedText = formattedText.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            formattedText = formattedText.replace(/\*(.*?)\*/g, '<em>$1</em>');
            formattedText = formattedText.replace(/^- (.*?)\n/gm, '<li>$1</li>');
            formattedText = formattedText.replace(/(<li>.*?<\/li>)/g, '<ul>$1</ul>');
            formattedText = formattedText.replace(/<\/ul>\s*<ul>/g, '');
            formattedText = formattedText.replace(/\n/g, '<br>');
        }
        
        messageDiv.innerHTML = `
            <div class="msg-bubble">${formattedText}</div>
        `;
        messagesArea.appendChild(messageDiv);
        messagesArea.scrollTop = messagesArea.scrollHeight;
    }
    
    async function sendUserQuery() {
        const query = chatInput.value.trim();
        if (!query || !activeProjectId) return;
        
        appendMessage(query, true);
        chatInput.value = '';
        
        const loaderDiv = document.createElement('div');
        loaderDiv.className = 'message incoming loader-msg';
        loaderDiv.innerHTML = '<div class="msg-bubble text-muted">L\'assistant réfléchit...</div>';
        messagesArea.appendChild(loaderDiv);
        messagesArea.scrollTop = messagesArea.scrollHeight;
        
        try {
            const res = await fetch(`/api/projects/${activeProjectId}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });
            const result = await res.json();
            
            loaderDiv.remove();
            
            if (result.success) {
                appendMessage(result.response, false);
            } else {
                appendMessage("Une erreur est survenue lors de la communication avec l'assistant.", false);
            }
        } catch (err) {
            loaderDiv.remove();
            appendMessage("Impossible de joindre le serveur Flask.", false);
        }
    }
    
    btnSendChat.addEventListener('click', sendUserQuery);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendUserQuery();
    });
    
    btnClearChat.addEventListener('click', () => {
        messagesArea.innerHTML = `
            <div class="message incoming">
                <div class="msg-bubble">
                    Discussion vidée. Comment puis-je vous aider aujourd'hui ?
                </div>
            </div>
        `;
    });

    // --- 10. UTILS D'ÉDITION & SUPPRESSION DE SESSION ---
    async function editSession(id) {
        showLoader();
        try {
            const session = await requestAPI(`/api/sessions/${id}`);
            editingSessionId = id;
            
            document.getElementById('saisie-title').value = session.title;
            document.getElementById('saisie-date').value = session.interview_date.split('T')[0];
            document.getElementById('saisie-interviewer').value = session.interviewer;
            document.getElementById('saisie-interviewee').value = session.interviewee_name_or_group;
            document.getElementById('saisie-type-session').value = session.session_type;
            document.getElementById('saisie-actor-category').value = session.actor_category;
            
            saisieQuestionnaireId.value = session.questionnaire_id;
            selectQuestionnaire.value = session.questionnaire_id;
            activeQuestionnaireId = session.questionnaire_id;
            
            await loadQuestionnairesList();
            renderQuestionsFields();
            
            session.answers.forEach(ans => {
                const inputEl = formInterviewSaisie.querySelector(`[name="q_${ans.question_id}"]`);
                if (inputEl) {
                    inputEl.value = ans.answer_text;
                }
            });
            
            document.querySelector('#tab-collecte h2').innerText = "Modifier l'Entretien";
            btnSubmitSaisie.innerText = "Mettre à jour l'Entretien";
            btnSubmitSaisie.classList.add('btn-warning');
            
            let btnCancelEdit = document.getElementById('btn-cancel-edit-session');
            if (!btnCancelEdit) {
                btnCancelEdit = document.createElement('button');
                btnCancelEdit.id = 'btn-cancel-edit-session';
                btnCancelEdit.type = 'button';
                btnCancelEdit.className = 'btn-secondary';
                btnCancelEdit.style.marginLeft = '12px';
                btnCancelEdit.innerText = "Annuler la modification";
                btnCancelEdit.addEventListener('click', cancelEditSession);
                btnSubmitSaisie.parentNode.appendChild(btnCancelEdit);
            }
            
            switchTab('collecte');
            showToast("Entretien chargé dans le formulaire !", "info");
        } catch (err) {
            console.error("Erreur de chargement d'édition :", err);
        } finally {
            hideLoader();
        }
    }
    
    function cancelEditSession() {
        editingSessionId = null;
        formInterviewSaisie.reset();
        dynamicQuestionsContainer.innerHTML = '<p class="text-muted text-center py-4">Veuillez d\'abord sélectionner un questionnaire dans le panneau de gauche.</p>';
        btnSubmitSaisie.disabled = true;
        btnSubmitSaisie.innerText = "Enregistrer l'Entretien";
        btnSubmitSaisie.classList.remove('btn-warning');
        selectQuestionnaire.value = "";
        activeQuestionnaireId = null;
        
        const btnCancelEdit = document.getElementById('btn-cancel-edit-session');
        if (btnCancelEdit) btnCancelEdit.remove();
        
        document.querySelector('#tab-collecte h2').innerText = "Saisie Individuelle & Collective";
        switchTab('dashboard');
        showToast("Modification annulée.", "info");
    }
    
    async function deleteSession(id, name) {
        openConfirmModal(
            name || `Entretien #${id}`,
            "Êtes-vous sûr de vouloir supprimer cet entretien ? Cette opération supprimera définitivement toutes les réponses et verbatims saisis.",
            async () => {
                try {
                    const res = await requestAPI(`/api/sessions/${id}`, { method: 'DELETE' });
                    if (res.success) {
                        showToast("Entretien supprimé avec succès !", "success");
                    }
                } catch (err) {
                    console.error("Erreur lors de la suppression de l'entretien :", err);
                }
            }
        );
    }

    // --- 11. GESTION DE L'AUTHENTIFICATION ---
    const authOverlay = document.getElementById('auth-overlay');
    const appWorkspace = document.getElementById('app-workspace');
    const formLogin = document.getElementById('form-login');
    const formRegister = document.getElementById('form-register');
    const tabLoginBtn = document.getElementById('tab-login-btn');
    const tabRegisterBtn = document.getElementById('tab-register-btn');
    const userAvatarInitials = document.getElementById('user-avatar-initials');
    const userDropdown = document.getElementById('user-dropdown');
    
    // Validation Client-Side Helpers
    function validateEmail(email) {
        return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    }
    
    function showError(inputEl, message) {
        const group = inputEl.closest('.form-group-floating');
        if (!group) return;
        const feedback = group.querySelector('.error-feedback');
        if (feedback) {
            feedback.innerText = message;
            feedback.classList.add('show');
        }
        inputEl.style.borderColor = 'var(--danger)';
    }
    
    function clearError(inputEl) {
        const group = inputEl.closest('.form-group-floating');
        if (!group) return;
        const feedback = group.querySelector('.error-feedback');
        if (feedback) {
            feedback.innerText = '';
            feedback.classList.remove('show');
        }
        inputEl.style.borderColor = '';
    }

    // Effacer toutes les erreurs et formulaires lors du changement d'onglet
    function resetAuthForms() {
        formLogin.reset();
        formRegister.reset();
        document.querySelectorAll('.error-feedback').forEach(el => {
            el.innerText = '';
            el.classList.remove('show');
        });
        document.querySelectorAll('.form-group-floating input').forEach(el => {
            el.style.borderColor = '';
        });
    }

    // Bascule d'onglets de connexion / inscription
    tabLoginBtn.addEventListener('click', () => {
        tabLoginBtn.classList.add('active');
        tabRegisterBtn.classList.remove('active');
        formLogin.style.display = 'flex';
        formRegister.style.display = 'none';
        resetAuthForms();
    });

    tabRegisterBtn.addEventListener('click', () => {
        tabRegisterBtn.classList.add('active');
        tabLoginBtn.classList.remove('active');
        formRegister.style.display = 'flex';
        formLogin.style.display = 'none';
        resetAuthForms();
    });

    // Toggle Password Visibility (icône œil)
    document.querySelectorAll('.btn-toggle-password').forEach(btn => {
        btn.addEventListener('click', () => {
            const wrapper = btn.closest('.password-wrapper');
            const input = wrapper.querySelector('input');
            const eyeClosed = btn.querySelector('.eye-closed');
            
            if (input.type === 'password') {
                input.type = 'text';
                eyeClosed.style.display = 'block';
            } else {
                input.type = 'password';
                eyeClosed.style.display = 'none';
            }
        });
    });

    // Mot de passe oublié (simulation)
    const btnForgotPassword = document.getElementById('btn-forgot-password');
    if (btnForgotPassword) {
        btnForgotPassword.addEventListener('click', (e) => {
            e.preventDefault();
            showToast("La réinitialisation du mot de passe sera disponible prochainement.", "info");
        });
    }

    // Validation en direct lors de la saisie
    const inputsToValidate = [
        { id: 'login-email', type: 'email' },
        { id: 'login-password', type: 'password_min' },
        { id: 'register-username', type: 'username' },
        { id: 'register-email', type: 'email' },
        { id: 'register-password', type: 'password_min' },
        { id: 'register-confirm-password', type: 'password_match' }
    ];

    inputsToValidate.forEach(item => {
        const input = document.getElementById(item.id);
        if (input) {
            input.addEventListener('input', () => {
                clearError(input);
                if (item.type === 'email' && input.value.trim() !== '') {
                    if (!validateEmail(input.value)) {
                        showError(input, "Adresse email non valide.");
                    }
                }
                if (item.type === 'password_min' && input.value.trim() !== '') {
                    if (input.value.length < 6) {
                        showError(input, "Le mot de passe doit faire au moins 6 caractères.");
                    }
                }
                if (item.type === 'username' && input.value.trim() !== '') {
                    if (input.value.trim().length < 3) {
                        showError(input, "Le nom doit faire au moins 3 caractères.");
                    }
                }
                if (item.type === 'password_match' && input.value.trim() !== '') {
                    const original = document.getElementById('register-password').value;
                    if (input.value !== original) {
                        showError(input, "Les mots de passe ne correspondent pas.");
                    }
                }
            });
        }
    });

    // Profil dropdown
    userAvatarInitials.addEventListener('click', (e) => {
        e.stopPropagation();
        userDropdown.style.display = userDropdown.style.display === 'none' ? 'block' : 'none';
    });

    document.addEventListener('click', () => {
        if (userDropdown) userDropdown.style.display = 'none';
    });

    userDropdown.addEventListener('click', (e) => {
        e.stopPropagation();
    });

    // Soumission Connexion
    formLogin.addEventListener('submit', async (e) => {
        e.preventDefault();
        const emailEl = document.getElementById('login-email');
        const passwordEl = document.getElementById('login-password');
        
        let isValid = true;
        
        if (!validateEmail(emailEl.value)) {
            showError(emailEl, "Veuillez entrer une adresse email valide.");
            isValid = false;
        }
        
        if (passwordEl.value.length < 6) {
            showError(passwordEl, "Le mot de passe doit contenir au moins 6 caractères.");
            isValid = false;
        }
        
        if (!isValid) return;
        
        try {
            showLoader();
            const res = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: emailEl.value, password: passwordEl.value })
            });
            const data = await res.json();
            if (data.success) {
                showToast("Connexion réussie !", "success");
                formLogin.reset();
                initializeUserSession(data.user);
            } else {
                showToast(data.message || "Identifiants incorrects.", "error");
                showError(passwordEl, data.message || "Identifiants incorrects.");
            }
        } catch (err) {
            showToast("Impossible de joindre le serveur.", "error");
        } finally {
            hideLoader();
        }
    });

    // Soumission Inscription
    formRegister.addEventListener('submit', async (e) => {
        e.preventDefault();
        const usernameEl = document.getElementById('register-username');
        const emailEl = document.getElementById('register-email');
        const passwordEl = document.getElementById('register-password');
        const confirmEl = document.getElementById('register-confirm-password');
        
        let isValid = true;
        
        if (usernameEl.value.trim().length < 3) {
            showError(usernameEl, "Le nom d'utilisateur doit contenir au moins 3 caractères.");
            isValid = false;
        }
        
        if (!validateEmail(emailEl.value)) {
            showError(emailEl, "Veuillez entrer une adresse email valide.");
            isValid = false;
        }
        
        if (passwordEl.value.length < 6) {
            showError(passwordEl, "Le mot de passe doit contenir au moins 6 caractères.");
            isValid = false;
        }
        
        if (confirmEl.value !== passwordEl.value) {
            showError(confirmEl, "Les mots de passe ne correspondent pas.");
            isValid = false;
        }
        
        if (!isValid) return;
        
        try {
            showLoader();
            const res = await fetch('/api/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    username: usernameEl.value.trim(), 
                    email: emailEl.value.trim(), 
                    password: passwordEl.value 
                })
            });
            const data = await res.json();
            if (data.success) {
                showToast("Compte créé avec succès !", "success");
                formRegister.reset();
                initializeUserSession(data.user);
            } else {
                showToast(data.message || "Erreur de création de compte.", "error");
                showError(emailEl, data.message || "Erreur de création de compte.");
            }
        } catch (err) {
            showToast("Impossible de joindre le serveur.", "error");
        } finally {
            hideLoader();
        }
    });

    // Déconnexion
    document.getElementById('btn-logout').addEventListener('click', async () => {
        try {
            showLoader();
            const res = await fetch('/api/logout', { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                showToast("Déconnexion réussie.", "info");
                currentUser = null;
                apiCache.clear();
                authOverlay.style.display = 'flex';
                appWorkspace.style.display = 'none';
            }
        } catch (err) {
            showToast("Erreur lors de la déconnexion.", "error");
        } finally {
            hideLoader();
        }
    });

    function initializeUserSession(user) {
        currentUser = user;
        authOverlay.style.display = 'none';
        appWorkspace.style.display = 'flex';
        
        // Initiales pour l'avatar
        const initials = user.username ? user.username.substring(0, 2).toUpperCase() : 'U';
        userAvatarInitials.innerText = initials;
        
        // Dropdown info
        document.getElementById('user-display-name').innerText = user.username;
        document.getElementById('user-display-email').innerText = user.email;
        
        // Charger les projets de l'utilisateur
        loadProjects(true).then(() => {
            loadDashboardData();
        });
    }

    async function checkUserSession() {
        try {
            const res = await fetch('/api/me');
            if (res.status === 200) {
                const data = await res.json();
                if (data.success) {
                    initializeUserSession(data.user);
                    return;
                }
            }
        } catch (err) {
            console.log("Session inactive.");
        }
        authOverlay.style.display = 'flex';
        appWorkspace.style.display = 'none';
    }

    // --- 12. PARTAGE DE QUESTIONNAIRE ---
    const shareModal = document.getElementById('modal-share');
    const formShare = document.getElementById('form-share-questionnaire');
    const btnShareQuestionnaire = document.getElementById('btn-share-questionnaire');
    const btnCloseShareModal = document.getElementById('btn-close-share-modal');
    const btnCloseSharePanel = document.getElementById('btn-close-share-panel');
    const collaboratorsList = document.getElementById('share-collaborators-list');
    
    if (btnShareQuestionnaire) {
        btnShareQuestionnaire.addEventListener('click', () => {
            if (!activeQuestionnaireId) return;
            shareModal.style.display = 'flex';
            loadCollaboratorsList();
        });
    }
    
    const hideShareModal = () => { shareModal.style.display = 'none'; };
    if (btnCloseShareModal) btnCloseShareModal.addEventListener('click', hideShareModal);
    if (btnCloseSharePanel) btnCloseSharePanel.addEventListener('click', hideShareModal);

    async function loadCollaboratorsList() {
        if (!activeQuestionnaireId) return;
        collaboratorsList.innerHTML = '<p class="text-muted text-center py-2">Chargement...</p>';
        
        try {
            const shares = await requestAPI(`/api/questionnaires/${activeQuestionnaireId}/shares`);
            collaboratorsList.innerHTML = '';
            
            if (shares.length === 0) {
                collaboratorsList.innerHTML = '<p class="text-muted text-center py-3">Aucun collaborateur pour le moment.</p>';
                return;
            }
            
            shares.forEach(s => {
                const div = document.createElement('div');
                div.className = 'collaborator-item';
                div.innerHTML = `
                    <div class="collaborator-info">
                        <span class="collaborator-email">${s.shared_with_email}</span>
                        <span class="collaborator-perm">Droit: ${s.permission === 'edit' ? 'Modification' : 'Lecture'}</span>
                    </div>
                    <button class="btn-revoke-share" data-uid="${s.shared_with_user_id}">Révoquer</button>
                `;
                
                div.querySelector('.btn-revoke-share').addEventListener('click', async () => {
                    try {
                        const res = await requestAPI(`/api/questionnaires/${activeQuestionnaireId}/share/${s.shared_with_user_id}`, {
                            method: 'DELETE'
                        });
                        if (res.success) {
                            showToast("Accès révoqué avec succès !", "success");
                            loadCollaboratorsList();
                        }
                    } catch (err) {
                        console.error(err);
                    }
                });
                
                collaboratorsList.appendChild(div);
            });
        } catch (err) {
            collaboratorsList.innerHTML = '<p class="text-muted text-center py-2 text-danger">Erreur de chargement.</p>';
        }
    }
    
    formShare.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('share-user-email').value;
        const permission = document.getElementById('share-permission').value;
        
        try {
            const res = await requestAPI(`/api/questionnaires/${activeQuestionnaireId}/share`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, permission })
            });
            if (res.success) {
                showToast("Questionnaire partagé avec succès !", "success");
                formShare.reset();
                loadCollaboratorsList();
            }
        } catch (err) {
            console.error(err);
        }
    });

    // --- 13. BASCOULEMENT DE THÈME (CLAIR / SOMBRE) ---
    const btnThemeToggle = document.getElementById('btn-theme-toggle');
    const sunIcon = document.getElementById('theme-icon-sun');
    const moonIcon = document.getElementById('theme-icon-moon');
    
    function applyTheme(theme) {
        if (theme === 'light') {
            document.body.classList.add('light-theme');
            sunIcon.style.display = 'block';
            moonIcon.style.display = 'none';
        } else {
            document.body.classList.remove('light-theme');
            sunIcon.style.display = 'none';
            moonIcon.style.display = 'block';
        }
        localStorage.setItem('theme', theme);
    }
    
    btnThemeToggle.addEventListener('click', () => {
        const currentTheme = document.body.classList.contains('light-theme') ? 'dark' : 'light';
        applyTheme(currentTheme);
        
        // Redessiner les graphiques pour adapter les couleurs si nécessaire
        const activeTab = document.querySelector('.nav-item.active').getAttribute('data-tab');
        if (activeTab === 'dashboard') {
            loadDashboardData();
        }
    });
    
    // Appliquer le thème initial au chargement
    const savedTheme = localStorage.getItem('theme') || (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
    applyTheme(savedTheme);

    // --- 14. EXPORTS DE DONNÉES CSV & EXCEL ---
    const setupExportButtons = () => {
        const triggers = [
            { id: 'btn-export-csv', type: 'csv' },
            { id: 'btn-export-excel', type: 'excel' },
            { id: 'btn-export-csv-tri', type: 'csv' },
            { id: 'btn-export-excel-tri', type: 'excel' }
        ];
        
        triggers.forEach(t => {
            const btn = document.getElementById(t.id);
            if (btn) {
                btn.addEventListener('click', () => {
                    if (!activeProjectId) return;
                    window.open(`/api/projects/${activeProjectId}/export/${t.type}`, '_blank');
                });
            }
        });
    };
    setupExportButtons();

    // --- ÉCOUTEUR SYNC DES ONGLETS (dataChanged) ---
    document.addEventListener('dataChanged', async (e) => {
        console.log("Synchronisation globale déclenchée par :", e.detail);
        
        // 1. Recharger les projets de façon transparente
        await loadProjects(false);
        
        // 2. Recharger l'onglet actif
        const activeTab = document.querySelector('.nav-item.active').getAttribute('data-tab');
        if (activeTab === 'dashboard') {
            loadDashboardData();
        } else if (activeTab === 'collecte') {
            loadQuestionnairesList();
        } else if (activeTab === 'analyse') {
            loadTriangulationData();
        }
    });

    // --- 15. INITIALISATION GENERALE ---
    checkUserSession();
});
