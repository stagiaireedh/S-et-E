/**
 * Application de Suivi-Évaluation - Triangulation de Données
 * Logique Frontend JavaScript
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
    
    function hideLoader() {
        const loader = document.getElementById('loader');
        if (loader) loader.style.display = 'none';
    }
    
    // --- CENTRALISATION DES APPELS API AVEC CACHE ET SYNC ---
    const apiCache = new Map();
    
    async function requestAPI(url, options = {}) {
        const method = options.method || 'GET';
        
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
                if (err.message !== "Authentification requise.") {
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
                if (err.message !== "Authentification requise.") {
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
    
    // Modals
    const modalProject = document.getElementById('modal-project');
    const modalQuestionnaire = document.getElementById('modal-questionnaire');
    
    // Formulaires
    const formNewProject = document.getElementById('form-new-project');
    const formNewQuestionnaire = document.getElementById('form-new-questionnaire');
    const formInterviewSaisie = document.getElementById('form-interview-saisie');

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
                projectTitle.innerText = "Aucun projet";
                projectDesc.innerText = "Veuillez créer un projet pour commencer.";
                activeProjectId = null;
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

            // Cacher ou afficher les boutons selon le flag is_demo
            const badgeDemo = document.getElementById('demo-badge');
            const btnDeleteProject = document.getElementById('btn-delete-project');
            const btnCreateQuestionnaire = document.getElementById('btn-create-questionnaire');
            
            if (proj.is_demo) {
                if (badgeDemo) badgeDemo.style.display = 'inline-block';
                if (btnDeleteProject) btnDeleteProject.style.display = 'none';
                if (btnCreateQuestionnaire) {
                    btnCreateQuestionnaire.disabled = true;
                    btnCreateQuestionnaire.title = "Le projet de démonstration est en lecture seule.";
                }
            } else {
                if (badgeDemo) badgeDemo.style.display = 'none';
                if (btnDeleteProject) btnDeleteProject.style.display = 'inline-flex';
                if (btnCreateQuestionnaire) {
                    btnCreateQuestionnaire.disabled = false;
                    btnCreateQuestionnaire.title = "";
                }
            }
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
        
        if (proj.is_demo) {
            showToast("Le projet de démonstration ne peut pas être supprimé.", "warning");
            return;
        }

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
        if (!activeProjectId) return;
        
        try {
            const sessions = await requestAPI(`/api/projects/${activeProjectId}/sessions`);
            const quests = await requestAPI(`/api/projects/${activeProjectId}/questionnaires`);
            const attachments = await requestAPI(`/api/projects/${activeProjectId}/attachments`);
            
            document.getElementById('kpi-total-sessions').innerText = sessions.length;
            document.getElementById('kpi-total-questionnaires').innerText = quests.length;
            document.getElementById('kpi-total-attachments').innerText = attachments.length;
            
            try {
                const triang = await requestAPI(`/api/projects/${activeProjectId}/triangulation`);
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
                const activeProj = projects.find(p => p.id === activeProjectId);
                const isDemo = activeProj && activeProj.is_demo;

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
                                ${isDemo ? '' : `
                                <button class="btn-link btn-edit-session" data-id="${s.id}" title="Modifier l'Entretien">
                                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7M18.5 2.5a2.121 2.121 0 1 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                                </button>
                                <button class="btn-link btn-delete-session" data-id="${s.id}" data-name="${s.title}" title="Supprimer l'Entretien">
                                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
                                </button>
                                `}
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
    
    dropZone.addEventListener('click', () => {
        const activeProj = projects.find(p => p.id === activeProjectId);
        if (activeProj && activeProj.is_demo) {
            showToast("Le projet de démonstration est en lecture seule.", "warning");
            return;
        }
        fileInput.click();
    });
    
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        const activeProj = projects.find(p => p.id === activeProjectId);
        if (activeProj && activeProj.is_demo) return;
        dropZone.classList.add('dragover');
    });
    
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });
    
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const activeProj = projects.find(p => p.id === activeProjectId);
        if (activeProj && activeProj.is_demo) {
            showToast("Le projet de démonstration est en lecture seule.", "warning");
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
        const activeProj = projects.find(p => p.id === activeProjectId);
        if (activeProj && activeProj.is_demo) {
            showToast("Le projet de démonstration est en lecture seule.", "warning");
            return;
        }
        
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
    const selectQuestionnaire = document.getElementById('collecte-questionnaire-select');
    const saisieQuestionnaireId = document.getElementById('saisie-questionnaire-id');
    const dynamicQuestionsContainer = document.getElementById('dynamic-questions-container');
    const btnSubmitSaisie = document.getElementById('btn-submit-saisie');
    
    // Charger questionnaires
    async function loadQuestionnairesList() {
        if (!activeProjectId) return;
        
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
        const proj = projects.find(p => p.id === activeProjectId);
        if (activeQuestionnaireId && proj && !proj.is_demo) {
            btnShare.style.display = 'block';
        } else {
            btnShare.style.display = 'none';
        }
    });
    
    function renderQuestionsFields() {
        const quest = questionnaires.find(q => q.id === activeQuestionnaireId);
        if (!quest) return;
        
        dynamicQuestionsContainer.innerHTML = '';
        btnSubmitSaisie.disabled = false;
        
        quest.questions.forEach(q => {
            const div = document.createElement('div');
            div.className = 'question-field-block';
            
            let inputHtml = '';
            if (q.question_type === 'select') {
                inputHtml = `<select name="q_${q.id}" class="custom-select" required>`;
                inputHtml += '<option value="" disabled selected>Sélectionner une option...</option>';
                q.choices.forEach(c => {
                    inputHtml += `<option value="${c}">${c}</option>`;
                });
                inputHtml += '</select>';
            } else {
                inputHtml = `<textarea name="q_${q.id}" rows="3" placeholder="Écrire la réponse textuelle de l'entretien..." required></textarea>`;
            }
            
            div.innerHTML = `
                <div class="form-group">
                    <label>${q.order_num}. ${q.text}</label>
                    ${inputHtml}
                </div>
            `;
            dynamicQuestionsContainer.appendChild(div);
        });
    }
    
    // Soumission formulaire saisie
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
            quest.questions.forEach(q => {
                const el = formInterviewSaisie.querySelector(`[name="q_${q.id}"]`);
                if (el) {
                    answers[q.id] = el.value;
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

                switchTab('dashboard');
            }
        } catch (err) {
            console.error("Erreur lors de la sauvegarde de l'entretien:", err);
        }
    });
    
    // --- MODAL CREATION DE QUESTIONNAIRE ---
    const btnCreateQuestionnaire = document.getElementById('btn-create-questionnaire');
    const btnAddQuestionRow = document.getElementById('btn-add-question-row');
    const questionsListDiv = document.getElementById('modal-questions-list');
    
    btnCreateQuestionnaire.addEventListener('click', () => {
        const activeProj = projects.find(p => p.id === activeProjectId);
        if (activeProj && activeProj.is_demo) {
            showToast("Le projet de démonstration est en lecture seule.", "warning");
            return;
        }
        modalQuestionnaire.classList.add('active');
        questionsListDiv.innerHTML = '';
        addQuestionRow();
    });
    
    document.getElementById('btn-close-quest-modal').addEventListener('click', () => modalQuestionnaire.classList.remove('active'));
    document.getElementById('btn-cancel-quest-modal').addEventListener('click', () => modalQuestionnaire.classList.remove('active'));
    
    function addQuestionRow() {
        const div = document.createElement('div');
        div.className = 'modal-question-row';
        div.innerHTML = `
            <input type="text" class="quest-text" placeholder="Entrez la question..." required>
            <select class="quest-type custom-select">
                <option value="text">Texte libre</option>
                <option value="select">Choix Unique</option>
            </select>
            <input type="text" class="quest-choices" placeholder="Option 1, Option 2 (séparées par virgules)" style="display:none; width: 220px;">
            <button type="button" class="btn-remove-row">&times;</button>
        `;
        
        const selectType = div.querySelector('.quest-type');
        const inputChoices = div.querySelector('.quest-choices');
        
        selectType.addEventListener('change', (e) => {
            if (e.target.value === 'select') {
                inputChoices.style.display = 'block';
                inputChoices.required = true;
            } else {
                inputChoices.style.display = 'none';
                inputChoices.required = false;
                inputChoices.value = '';
            }
        });
        
        div.querySelector('.btn-remove-row').addEventListener('click', () => {
            div.remove();
        });
        
        questionsListDiv.appendChild(div);
    }
    
    btnAddQuestionRow.addEventListener('click', addQuestionRow);
    
    formNewQuestionnaire.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const title = document.getElementById('new-quest-title').value;
        const description = document.getElementById('new-quest-desc').value;
        
        const questionRows = questionsListDiv.querySelectorAll('.modal-question-row');
        const questions = [];
        
        questionRows.forEach(row => {
            const text = row.querySelector('.quest-text').value;
            const question_type = row.querySelector('.quest-type').value;
            const choices = row.querySelector('.quest-choices').value;
            
            questions.push({ text, question_type, choices });
        });
        
        if (questions.length === 0) {
            showToast("Veuillez ajouter au moins une question.", "warning");
            return;
        }
        
        const payload = { title, description, questions };
        
        try {
            const result = await requestAPI(`/api/projects/${activeProjectId}/questionnaires`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (result.success) {
                modalQuestionnaire.classList.remove('active');
                formNewQuestionnaire.reset();
                showToast("Questionnaire créé avec succès !", "success");
                loadQuestionnairesList();
            }
        } catch (err) {
            console.error("Erreur lors de la création du questionnaire:", err);
        }
    });

    // --- 8. ANGLAIS ANALYSE TRIANGULATION & MATRICE ---
    const selectCompareQuestion = document.getElementById('compare-question-select');
    const matrixContainer = document.getElementById('triangulation-matrix-cards');
    let analysisDataGlobal = null;
    
    async function loadTriangulationData() {
        if (!activeProjectId) return;
        
        try {
            const data = await requestAPI(`/api/projects/${activeProjectId}/triangulation`);
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
    
    // Bascule d'onglets de connexion / inscription
    tabLoginBtn.addEventListener('click', () => {
        tabLoginBtn.classList.add('active');
        tabRegisterBtn.classList.remove('active');
        formLogin.style.display = 'flex';
        formRegister.style.display = 'none';
    });

    tabRegisterBtn.addEventListener('click', () => {
        tabRegisterBtn.classList.add('active');
        tabLoginBtn.classList.remove('active');
        formRegister.style.display = 'flex';
        formLogin.style.display = 'none';
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
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;
        
        try {
            showLoader();
            const res = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            const data = await res.json();
            if (data.success) {
                showToast("Connexion réussie !", "success");
                formLogin.reset();
                initializeUserSession(data.user);
            } else {
                showToast(data.message || "Identifiants incorrects.", "error");
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
        const username = document.getElementById('register-username').value;
        const email = document.getElementById('register-email').value;
        const password = document.getElementById('register-password').value;
        
        try {
            showLoader();
            const res = await fetch('/api/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, email, password })
            });
            const data = await res.json();
            if (data.success) {
                showToast("Compte créé avec succès !", "success");
                formRegister.reset();
                initializeUserSession(data.user);
            } else {
                showToast(data.message || "Erreur de création de compte.", "error");
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
