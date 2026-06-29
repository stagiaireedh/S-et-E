/**
 * Application de Suivi-Évaluation - Triangulation de Données
 * Logique Frontend JavaScript
 */

document.addEventListener('DOMContentLoaded', () => {
    // --- VARIABLES DE L'APPLICATION ---
    let activeProjectId = null;
    let activeQuestionnaireId = null;
    let projects = [];
    let questionnaires = [];
    let charts = {}; // Stockage des instances de Chart.js pour pouvoir les mettre à jour
    
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
    async function loadProjects() {
        try {
            const res = await fetch('/api/projects');
            projects = await res.json();
            
            projectSelect.innerHTML = '';
            if (projects.length === 0) {
                projectSelect.innerHTML = '<option value="" disabled selected>Créer un projet d\'abord</option>';
                projectTitle.innerText = "Aucun projet";
                projectDesc.innerText = "Veuillez créer un projet pour commencer.";
                return;
            }
            
            projects.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.id;
                opt.innerText = p.name;
                projectSelect.appendChild(opt);
            });
            
            // Sélectionner le premier projet par défaut ou réutiliser le dernier actif
            const savedProjectId = localStorage.getItem('activeProjectId');
            if (savedProjectId && projects.some(p => p.id == savedProjectId)) {
                activeProjectId = parseInt(savedProjectId);
            } else {
                activeProjectId = projects[0].id;
            }
            
            projectSelect.value = activeProjectId;
            updateActiveProjectDetails();
            loadDashboardData();
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
        }
    }
    
    projectSelect.addEventListener('change', (e) => {
        activeProjectId = parseInt(e.target.value);
        updateActiveProjectDetails();
        
        // Recharger les données de l'onglet actif
        const activeTab = document.querySelector('.nav-item.active').getAttribute('data-tab');
        switchTab(activeTab);
    });
    
    // Modals Projet
    btnNewProject.addEventListener('click', () => modalProject.classList.add('active'));
    document.getElementById('btn-close-project-modal').addEventListener('click', () => modalProject.classList.remove('active'));
    document.getElementById('btn-cancel-project-modal').addEventListener('click', () => modalProject.classList.remove('active'));
    
    formNewProject.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('new-project-name').value;
        const description = document.getElementById('new-project-desc').value;
        
        try {
            const res = await fetch('/api/projects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, description })
            });
            const result = await res.json();
            if (result.success) {
                modalProject.classList.remove('active');
                formNewProject.reset();
                // Recharger et forcer la sélection du nouveau projet
                localStorage.setItem('activeProjectId', result.project.id);
                await loadProjects();
            }
        } catch (err) {
            alert("Erreur lors de la création du projet.");
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
            // 1. Charger les métriques globales
            const resSessions = await fetch(`/api/projects/${activeProjectId}/sessions`);
            const sessions = await resSessions.json();
            
            const resQuests = await fetch(`/api/projects/${activeProjectId}/questionnaires`);
            const quests = await resQuests.json();
            
            const resAtts = await fetch(`/api/projects/${activeProjectId}/attachments`);
            const attachments = await resAtts.json();
            
            document.getElementById('kpi-total-sessions').innerText = sessions.length;
            document.getElementById('kpi-total-questionnaires').innerText = quests.length;
            document.getElementById('kpi-total-attachments').innerText = attachments.length;
            
            // 2. Charger triangulation IA pour le KPI sentiment
            try {
                const resTriang = await fetch(`/api/projects/${activeProjectId}/triangulation`);
                const triang = await resTriang.json();
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
            
            // 3. Remplir le tableau des entretiens récents
            const tbody = document.querySelector('#table-recent-sessions tbody');
            tbody.innerHTML = '';
            
            if (sessions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Aucun entretien enregistré.</td></tr>';
            } else {
                // Prendre les 5 sessions les plus récentes
                sessions.slice(0, 5).forEach(s => {
                    const tr = document.createElement('tr');
                    
                    // Calcul d'un sentiment individuel moyen pour la ligne
                    let individualScore = 0;
                    if (s.answers.length > 0) {
                        // Simulation rapide du sentiment de l'entretien (sera amélioré)
                        const scoreSum = s.answers.reduce((acc, a) => {
                            // Détection simpliste côté JS pour affichage rapide
                            if (a.answer_text.toLowerCase().includes('panne') || a.answer_text.toLowerCase().includes('difficile') || a.answer_text.toLowerCase().includes('problème')) return acc - 0.5;
                            if (a.answer_text.toLowerCase().includes('bon') || a.answer_text.toLowerCase().includes('excellent') || a.answer_text.toLowerCase().includes('très bien')) return acc + 0.5;
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
                    
                    // Formater la date en français (JJ/MM/AAAA)
                    const dateObj = new Date(s.interview_date);
                    const formattedDate = dateObj.toLocaleDateString('fr-FR');
                    
                    tr.innerHTML = `
                        <td>${formattedDate}</td>
                        <td><strong>${s.title}</strong><br><small class="text-muted">${s.interviewee_name_or_group}</small></td>
                        <td>${s.actor_category}</td>
                        <td><span class="badge ${s.session_type === 'collectif' ? 'badge-warning' : 'badge-info'}">${s.session_type}</span></td>
                        <td><span class="badge ${badgeClass}">${interpretLabel}</span></td>
                        <td>
                            <button class="btn-link btn-download-session-pdf" data-id="${s.id}" title="Télécharger Fiche PDF">
                                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
                            </button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
                
                // Ajouter écouteurs de téléchargement pour chaque fiche
                document.querySelectorAll('.btn-download-session-pdf').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        const sId = btn.getAttribute('data-id');
                        window.open(`/api/sessions/${sId}/report`, '_blank');
                    });
                });
            }
            
            // 4. Charger et afficher la liste des pièces jointes
            renderAttachments(attachments);
            
            // 5. Générer les graphiques
            renderDashboardCharts(sessions);
            
        } catch (err) {
            console.error("Erreur de chargement du dashboard:", err);
        }
    }
    
    btnQuickSaisie.addEventListener('click', () => switchTab('collecte'));
    
    // --- 5. RENDER DES GRAPHIQUES (CHART.JS) ---
    function renderDashboardCharts(sessions) {
        // Graphique 1: Distribution des Acteurs (Pie/Doughnut)
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
        
        if (charts.actors) charts.actors.destroy(); // Détruire l'ancienne instance
        
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
        
        // Graphique 2: Tendance des Sentiments (Chronologique)
        // Trier les sessions par date
        const sortedSessions = [...sessions].sort((a, b) => new Date(a.interview_date) - new Date(b.interview_date));
        
        const chartLabels = [];
        const chartData = [];
        
        sortedSessions.forEach(s => {
            const dateObj = new Date(s.interview_date);
            chartLabels.push(dateObj.toLocaleDateString('fr-FR', { month: 'short', day: 'numeric' }));
            
            // Calcul rapide de sentiment individuel
            let score = 0;
            if (s.answers.length > 0) {
                const scoreSum = s.answers.reduce((acc, a) => {
                    if (a.answer_text.toLowerCase().includes('panne') || a.answer_text.toLowerCase().includes('difficile') || a.answer_text.toLowerCase().includes('problème')) return acc - 0.5;
                    if (a.answer_text.toLowerCase().includes('bon') || a.answer_text.toLowerCase().includes('excellent') || a.answer_text.toLowerCase().includes('très bien')) return acc + 0.5;
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
    
    dropZone.addEventListener('click', () => fileInput.click());
    
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });
    
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });
    
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
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
        
        for (let i = 0; i < files.length; i++) {
            const formData = new FormData();
            formData.append('file', files[i]);
            
            try {
                const res = await fetch(`/api/projects/${activeProjectId}/attachments`, {
                    method: 'POST',
                    body: formData
                });
                const result = await res.json();
                if (!result.success) {
                    alert(`Échec de l'upload : ${result.message}`);
                }
            } catch (err) {
                console.error("Erreur d'upload:", err);
            }
        }
        
        // Recharger les fichiers
        const res = await fetch(`/api/projects/${activeProjectId}/attachments`);
        const attachments = await res.json();
        renderAttachments(attachments);
        
        // Mettre à jour le KPI
        document.getElementById('kpi-total-attachments').innerText = attachments.length;
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
            
            const isPdf = att.filename.toLowerCase().endsWith('.pdf');
            
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
            const res = await fetch(`/api/projects/${activeProjectId}/questionnaires`);
            questionnaires = await res.json();
            
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
        
        // Collecte des réponses aux questions
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
        
        try {
            const res = await fetch(`/api/projects/${activeProjectId}/sessions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await res.json();
            if (result.success) {
                alert("Entretien enregistré avec succès !");
                formInterviewSaisie.reset();
                dynamicQuestionsContainer.innerHTML = '<p class="text-muted text-center py-4">Veuillez d\'abord sélectionner un questionnaire dans le panneau de gauche.</p>';
                btnSubmitSaisie.disabled = true;
                activeQuestionnaireId = null;
                selectQuestionnaire.value = "";
                
                // Rediriger vers le dashboard
                switchTab('dashboard');
            }
        } catch (err) {
            alert("Erreur lors de l'enregistrement de l'entretien.");
        }
    });
    
    // --- MODAL CREATION DE QUESTIONNAIRE ---
    const btnCreateQuestionnaire = document.getElementById('btn-create-questionnaire');
    const btnAddQuestionRow = document.getElementById('btn-add-question-row');
    const questionsListDiv = document.getElementById('modal-questions-list');
    
    btnCreateQuestionnaire.addEventListener('click', () => {
        modalQuestionnaire.classList.add('active');
        questionsListDiv.innerHTML = '';
        addQuestionRow(); // Ajouter une première ligne par défaut
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
        
        // Masquer/Afficher les choix selon le type sélectionné
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
        
        // Suppression de ligne
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
            alert("Veuillez ajouter au moins une question.");
            return;
        }
        
        const payload = { title, description, questions };
        
        try {
            const res = await fetch(`/api/projects/${activeProjectId}/questionnaires`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await res.json();
            if (result.success) {
                modalQuestionnaire.classList.remove('active');
                formNewQuestionnaire.reset();
                loadQuestionnairesList();
            }
        } catch (err) {
            alert("Erreur lors de la création du questionnaire.");
        }
    });

    // --- 8. ANGLAIS ANALYSE TRIANGULATION & MATRICE ---
    const selectCompareQuestion = document.getElementById('compare-question-select');
    const matrixContainer = document.getElementById('triangulation-matrix-cards');
    let analysisDataGlobal = null;
    
    async function loadTriangulationData() {
        if (!activeProjectId) return;
        
        try {
            const res = await fetch(`/api/projects/${activeProjectId}/triangulation`);
            const data = await res.json();
            analysisDataGlobal = data;
            
            if (!data.success) {
                // Pas assez de données
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
            
            // 1. Sentiment Gauge
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
            
            // 2. Thèmes récurrents
            const themesDiv = document.getElementById('ai-themes-list');
            themesDiv.innerHTML = '';
            
            // Trouver le poids maximum pour afficher le pourcentage relatif des barres
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
            
            // 3. Recommandations
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
            
            // 4. Charger les questions dans le sélecteur matriciel comparatif
            loadCompareQuestions();
            
        } catch (err) {
            console.error("Erreur de chargement triangulation:", err);
        }
    }
    
    async function loadCompareQuestions() {
        if (!activeProjectId) return;
        
        try {
            // Récupérer le premier questionnaire pour lister ses questions
            const res = await fetch(`/api/projects/${activeProjectId}/questionnaires`);
            const quests = await res.json();
            if (quests.length === 0) {
                selectCompareQuestion.innerHTML = '<option value="" disabled selected>Aucun questionnaire...</option>';
                return;
            }
            
            // Prendre le premier questionnaire actif par défaut
            const firstQuest = quests[0];
            selectCompareQuestion.innerHTML = '';
            
            firstQuest.questions.forEach(q => {
                const opt = document.createElement('option');
                opt.value = q.id;
                opt.innerText = `${q.order_num}. ${q.text.substring(0, 70)}...`;
                selectCompareQuestion.appendChild(opt);
            });
            
            // Rendre le tableau matriciel initialisé
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
            // Récupérer toutes les sessions d'entretiens du projet
            const res = await fetch(`/api/projects/${activeProjectId}/sessions`);
            const sessions = await res.json();
            
            // Organiser les réponses par catégorie d'acteur
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
            
            // Vider l'affichage
            matrixContainer.innerHTML = '';
            
            // Pour chaque acteur, s'il y a des réponses, afficher
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
        
        // Conversion de markdown très simple en HTML pour les retours à la ligne, listes et gras
        let formattedText = text;
        if (!isOutgoing) {
            // Remplacer les titres en gras Markdown
            formattedText = formattedText.replace(/### (.*?)\n/g, '<h4>$1</h4>');
            formattedText = formattedText.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            formattedText = formattedText.replace(/\*(.*?)\*/g, '<em>$1</em>');
            // Listes
            formattedText = formattedText.replace(/^- (.*?)\n/gm, '<li>$1</li>');
            formattedText = formattedText.replace(/(<li>.*?<\/li>)/g, '<ul>$1</ul>');
            // Nettoyer les balises multiples d'UL
            formattedText = formattedText.replace(/<\/ul>\s*<ul>/g, '');
            // Retours chariots simples
            formattedText = formattedText.replace(/\n/g, '<br>');
        }
        
        messageDiv.innerHTML = `
            <div class="msg-bubble">${formattedText}</div>
        `;
        messagesArea.appendChild(messageDiv);
        
        // Défilement automatique vers le bas
        messagesArea.scrollTop = messagesArea.scrollHeight;
    }
    
    async function sendUserQuery() {
        const query = chatInput.value.trim();
        if (!query || !activeProjectId) return;
        
        appendMessage(query, true);
        chatInput.value = '';
        
        // Afficher indicateur de chargement
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
            
            // Retirer le loader
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

    // --- 10. INITIALISATION GENERALE ---
    loadProjects();
});
