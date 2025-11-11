#!/bin/bash
# =============================================================================
# Helmitex Warehouse - Production Deploy Script
# =============================================================================
# Автоматический деплой приложения с безопасностью и откатом
#
# Использование:
#   ./deploy.sh                    # Полный деплой
#   ./deploy.sh --skip-backup      # Деплой без бэкапа БД
#   ./deploy.sh --rollback         # Откат к предыдущей версии
# =============================================================================

set -e  # Остановка при любой ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Конфигурация
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${PROJECT_DIR}/backups"
LOG_FILE="${PROJECT_DIR}/deploy.log"
COMPOSE_FILE="${PROJECT_DIR}/docker-compose.yml"

# Создание директории для бэкапов
mkdir -p "${BACKUP_DIR}"

# =============================================================================
# Функции логирования
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "${LOG_FILE}"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "${LOG_FILE}"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "${LOG_FILE}"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "${LOG_FILE}"
}

# =============================================================================
# Функция бэкапа базы данных
# =============================================================================

backup_database() {
    log_info "Creating database backup..."

    local backup_file="${BACKUP_DIR}/db_backup_$(date +%Y%m%d_%H%M%S).sql"

    # Экспорт базы через docker exec
    if docker compose exec -T db pg_dump -U warehouse warehouse > "${backup_file}" 2>/dev/null; then
        log_success "Database backup created: ${backup_file}"

        # Сжатие бэкапа
        gzip "${backup_file}"
        log_success "Backup compressed: ${backup_file}.gz"

        # Удаление старых бэкапов (старше 7 дней)
        find "${BACKUP_DIR}" -name "db_backup_*.sql.gz" -mtime +7 -delete
        log_info "Old backups cleaned (>7 days)"
    else
        log_warning "Database backup failed or database is not running"
    fi
}

# =============================================================================
# Функция проверки здоровья контейнеров
# =============================================================================

check_health() {
    log_info "Checking container health..."

    # Ждем 15 секунд для запуска контейнеров
    sleep 15

    # Проверка статуса контейнеров
    if docker compose ps | grep -q "Up"; then
        log_success "Containers are running"

        # Показываем статус
        docker compose ps

        # Проверка логов бота на наличие критических ошибок
        if docker compose logs bot --tail=50 | grep -qi "error\|critical\|exception"; then
            log_warning "Found errors in bot logs. Please check:"
            docker compose logs bot --tail=20
        else
            log_success "No critical errors found in logs"
        fi

        return 0
    else
        log_error "Containers are not running properly"
        docker compose ps
        return 1
    fi
}

# =============================================================================
# Функция отката
# =============================================================================

rollback() {
    log_warning "Rolling back to previous version..."

    # Остановка текущих контейнеров
    docker compose down

    # Откат git к предыдущему коммиту
    git reset --hard HEAD~1

    # Перезапуск
    docker compose up -d --build

    if check_health; then
        log_success "Rollback completed successfully"
    else
        log_error "Rollback failed. Manual intervention required!"
        exit 1
    fi
}

# =============================================================================
# Главная функция деплоя
# =============================================================================

deploy() {
    local skip_backup=false

    # Парсинг аргументов
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-backup)
                skip_backup=true
                shift
                ;;
            --rollback)
                rollback
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    log_info "========================================="
    log_info "🚀 Starting Helmitex Warehouse Deployment"
    log_info "========================================="
    log_info "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
    log_info "Project dir: ${PROJECT_DIR}"

    # Проверка наличия docker-compose
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed!"
        exit 1
    fi

    # Проверка docker compose или docker-compose
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    elif docker-compose --version &> /dev/null; then
        COMPOSE_CMD="docker-compose"
    else
        log_error "Docker Compose is not installed!"
        exit 1
    fi
    log_info "Using: ${COMPOSE_CMD}"

    # Переход в директорию проекта
    cd "${PROJECT_DIR}"

    # Бэкап базы данных (если не пропущен)
    if [ "$skip_backup" = false ]; then
        backup_database
    else
        log_warning "Skipping database backup"
    fi

    # Сохранение текущего коммита для возможности отката
    local current_commit=$(git rev-parse HEAD)
    log_info "Current commit: ${current_commit}"

    # Обновление кода из Git
    log_info "Pulling latest code from repository..."
    if git pull origin main; then
        log_success "Code updated successfully"
    else
        log_error "Failed to pull code from repository"
        exit 1
    fi

    # Показываем изменения
    local new_commit=$(git rev-parse HEAD)
    if [ "$current_commit" != "$new_commit" ]; then
        log_info "Changes deployed:"
        git log --oneline "${current_commit}..${new_commit}"
    else
        log_info "No new commits to deploy"
    fi

    # Остановка текущих контейнеров
    log_info "Stopping current containers..."
    $COMPOSE_CMD down

    # Сборка новых образов
    log_info "Building Docker images..."
    if $COMPOSE_CMD build --no-cache; then
        log_success "Images built successfully"
    else
        log_error "Failed to build images"
        rollback
        exit 1
    fi

    # Запуск контейнеров
    log_info "Starting containers..."
    if $COMPOSE_CMD up -d; then
        log_success "Containers started"
    else
        log_error "Failed to start containers"
        rollback
        exit 1
    fi

    # Проверка здоровья
    if check_health; then
        log_success "========================================="
        log_success "✅ Deployment completed successfully!"
        log_success "========================================="

        # Показываем статус
        log_info "Container status:"
        $COMPOSE_CMD ps

        # Показываем последние логи
        log_info "Recent logs:"
        $COMPOSE_CMD logs --tail=30 bot

        return 0
    else
        log_error "Health check failed. Rolling back..."
        rollback
        exit 1
    fi
}

# =============================================================================
# Обработчик ошибок
# =============================================================================

trap 'log_error "Deployment failed at line $LINENO. Check logs: ${LOG_FILE}"' ERR

# =============================================================================
# Запуск
# =============================================================================

deploy "$@"
