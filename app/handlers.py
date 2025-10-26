from typing import Dict, Tuple
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from .config import TELEGRAM_BOT_TOKEN, OWNER_TELEGRAM_ID
from .db import SessionLocal, init_db
from .models import SKUType, RecipeStatus
from . import services
from .utils import parse_key_value_lines

# States
(
    SKU_ADD_TYPE, SKU_ADD_CODE, SKU_ADD_NAME, SKU_ADD_CATEGORY, SKU_ADD_PACK_WEIGHT,
    CAT_ADD_NAME,
    RECIPE_PRODUCT, RECIPE_TYIELD, RECIPE_COMPONENTS,
    PRODUCE_PRODUCT, PRODUCE_BARREL, PRODUCE_TARGET, PRODUCE_FACT_COMPONENTS, PRODUCE_FACT_MASS, PRODUCE_SAVE_TK
) = range(15)

def db_session():
    return SessionLocal()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Складской бот (MVP)\n\n"
        "Команды:\n"
        "/sku_add — добавить позицию номенклатуры\n"
        "/sku_list — список номенклатуры\n"
        "/category_add — добавить категорию сырья\n"
        "/category_list — список категорий\n"
        "/recipe_new — создать ТК (для полуфабриката)\n"
        "/recipe_list — список ТК\n"
        "/produce — замес по ТК (целевой вес в бочке)\n"
        "/tk_drafts — (владелец) черновики ТК\n"
        "/tk_activate <id> — (владелец) активировать ТК\n"
    )
    await update.message.reply_text(text)

# Category add/list
async def category_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Название категории сырья:")
    return CAT_ADD_NAME

async def category_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    db = db_session()
    try:
        cat = services.add_category(db, name)
        await update.message.reply_text(f"Категория добавлена: {cat.name}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")
    finally:
        db.close()
    return ConversationHandler.END

async def category_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = db_session()
    try:
        cats = services.list_categories(db)
        if not cats:
            await update.message.reply_text("Категории: пусто.")
            return
        await update.message.reply_text("Категории:\n" + "\n".join([f"- {c.name}" for c in cats]))
    finally:
        db.close()

# SKU add/list
async def sku_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Тип позиции? Введите: raw | semi | finished")
    return SKU_ADD_TYPE

async def sku_add_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text.strip().lower()
    if t not in ("raw","semi","finished"):
        await update.message.reply_text("Только raw | semi | finished. Повторите:")
        return SKU_ADD_TYPE
    context.user_data["sku_type"] = t
    await update.message.reply_text("Код позиции (уникальный):")
    return SKU_ADD_CODE

async def sku_add_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sku_code"] = update.message.text.strip()
    await update.message.reply_text("Наименование:")
    return SKU_ADD_NAME

async def sku_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["sku_name"] = update.message.text.strip()
    t = context.user_data["sku_type"]
    if t == "raw":
        await update.message.reply_text("Категория (существующее имя категории сырья):")
        return SKU_ADD_CATEGORY
    elif t == "finished":
        await update.message.reply_text("Вес единицы (г, число):")
        return SKU_ADD_PACK_WEIGHT
    else:
        db = db_session()
        try:
            sku = services.add_sku(db,
                code=context.user_data["sku_code"],
                name=context.user_data["sku_name"],
                type_=SKUType.semi,
                base_unit="kg",
                pack_weight_g=None,
                category_name=None
            )
            await update.message.reply_text(f"Добавлено: {sku.code} — {sku.name} (semi)")
        except Exception as e:
            await update.message.reply_text(f"Ошибка: {e}")
        finally:
            db.close()
        return ConversationHandler.END

async def sku_add_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category_name = update.message.text.strip()
    db = db_session()
    try:
        sku = services.add_sku(db,
            code=context.user_data["sku_code"],
            name=context.user_data["sku_name"],
            type_=SKUType.raw,
            base_unit="kg",
            pack_weight_g=None,
            category_name=category_name
        )
        await update.message.reply_text(f"Добавлено: {sku.code} — {sku.name} (raw, категория: {category_name})")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")
    finally:
        db.close()
    return ConversationHandler.END

async def sku_add_pack_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        pw = float(update.message.text.strip().replace(",", "."))
    except:
        await update.message.reply_text("Введите число (граммы):")
        return SKU_ADD_PACK_WEIGHT
    db = db_session()
    try:
        sku = services.add_sku(db,
            code=context.user_data["sku_code"],
            name=context.user_data["sku_name"],
            type_=SKUType.finished,
            base_unit="pcs",
            pack_weight_g=pw,
            category_name=None
        )
        await update.message.reply_text(f"Добавлено: {sku.code} — {sku.name} (finished, {pw} г)")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")
    finally:
        db.close()
    return ConversationHandler.END

async def sku_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = db_session()
    try:
        skus = services.list_skus(db)
        if not skus:
            await update.message.reply_text("Номенклатура пуста.")
            return
        lines = []
        for s in skus:
            cat = f" | cat:{s.category.name}" if s.category else ""
            pw = f" | {int(s.pack_weight_g)}g" if s.pack_weight_g else ""
            lines.append(f"- {s.code} | {s.name} | {s.type} | unit:{s.base_unit}{pw}{cat}")
        await update.message.reply_text("Номенклатура:\n" + "\n".join(lines))
    finally:
        db.close()

# Recipes
async def recipe_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Код полуфабриката (type=semi):")
    return RECIPE_PRODUCT

async def recipe_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["recipe_product"] = update.message.text.strip()
    await update.message.reply_text("Теоретический выход, % (например 100):")
    return RECIPE_TYIELD

async def recipe_yield(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        y = float(update.message.text.strip().replace(",", "."))
    except:
        await update.message.reply_text("Введите число, например 100:")
        return RECIPE_TYIELD
    context.user_data["recipe_yield"] = y
    await update.message.reply_text(
        "Компоненты (Категория: процент) построчно. Пример:\n"
        "Вода: 19.9\nНаполнители: 57\n...\nСумма = 100. Отправьте одним сообщением."
    )
    return RECIPE_COMPONENTS

async def recipe_components(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mapping = parse_key_value_lines(update.message.text)
    total = sum(mapping.values())
    if abs(total - 100.0) > 1e-9:
        await update.message.reply_text(f"Сумма = {total}, должна быть 100. Попробуйте снова.")
        return RECIPE_COMPONENTS
    db = db_session()
    try:
        comps = [(k, v) for k, v in mapping.items()]
        r = services.create_recipe(db, context.user_data["recipe_product"], context.user_data["recipe_yield"], comps, status=RecipeStatus.active)
        await update.message.reply_text(f"ТК создана и активирована (id={r.id})")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")
    finally:
        db.close()
    return ConversationHandler.END

async def recipe_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = db_session()
    try:
        rs = services.list_recipes(db)
        if not rs:
            await update.message.reply_text("ТК нет.")
            return
        out = []
        for r in rs:
            comps = [f"{rc.category.name}:{rc.percent:g}%" for rc in r.components]
            out.append(f"id={r.id} | {r.product.name} | статус: {r.status} | вых:{r.theoretical_yield_pct:g}% | [{', '.join(comps)}]")
        await update.message.reply_text("ТК:\n" + "\n".join(out))
    finally:
        db.close()

# Produce
async def produce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Код полуфабриката (type=semi):")
    return PRODUCE_PRODUCT

async def produce_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["prod_product"] = update.message.text.strip()
    await update.message.reply_text("Код бочки (создастся, если нет):")
    return PRODUCE_BARREL

async def produce_barrel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["prod_barrel"] = update.message.text.strip()
    await update.message.reply_text("Целевая масса в бочке, кг:")
    return PRODUCE_TARGET

async def produce_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target = float(update.message.text.strip().replace(",", "."))
    except:
        await update.message.reply_text("Введите число (кг):")
        return PRODUCE_TARGET

    db = db_session()
    try:
        recipe = services.get_active_recipe(db, context.user_data["prod_product"])
        if not recipe:
            await update.message.reply_text("Нет активной ТК для этого полуфабриката.")
            db.close()
            return ConversationHandler.END
        plan = services.compute_plan_from_target_mass(target, recipe.theoretical_yield_pct, recipe.components)
        context.user_data["prod_target_mass"] = target
        context.user_data["prod_ty"] = recipe.theoretical_yield_pct
        context.user_data["prod_plan_categories"] = list(plan.keys())

        lines = ["План ввода по категориям (кг), без округлений:"]
        for k,v in plan.items():
            lines.append(f"- {k}: {v}")
        lines += [
            "",
            "Теперь отправьте фактическое сырьё построчно в формате:",
            "Категория | raw_code: кг",
            "Пример:",
            "Вода | WATER: 19.9",
            "Наполнители | MK40: 30",
            "Наполнители | MK100: 27",
        ]
        await update.message.reply_text("\n".join(lines))
    finally:
        db.close()
    return PRODUCE_FACT_COMPONENTS

async def produce_fact_components(update: Update, context: ContextTypes.DEFAULT_TYPE):
    used: Dict[str, Tuple[str, float]] = {}
    ok = True
    for line in update.message.text.splitlines():
        if "|" in line and ":" in line:
            left, qtys = line.split(":", 1)
            cat, raw = left.split("|", 1)
            cat = cat.strip()
            raw = raw.strip()
            try:
                qty = float(qtys.strip().replace(",", "."))
            except:
                ok = False
                break
            if cat in used:
                # суммируем по категории, марку оставляем первую
                raw0, q0 = used[cat]
                used[cat] = (raw0, q0 + qty)
            else:
                used[cat] = (raw, qty)
        elif line.strip() == "":
            continue
        else:
            ok = False
            break
    if not ok or not used:
        await update.message.reply_text("Формат неверен. Повторите ввод.")
        return PRODUCE_FACT_COMPONENTS

    context.user_data["prod_used_raw"] = used
    await update.message.reply_text("Фактическая масса в бочке, кг (число):")
    return PRODUCE_FACT_MASS

async def produce_fact_mass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        fact_mass = float(update.message.text.strip().replace(",", "."))
    except:
        await update.message.reply_text("Введите число (кг):")
        return PRODUCE_FACT_MASS
    context.user_data["prod_fact_mass"] = fact_mass

    await update.message.reply_text(
        "Сохранить отклонения как новую ТК (Черновик)? Введите: yes | no\n"
        "(Предложение показывается при любых изменениях от активной ТК.)"
    )
    return PRODUCE_SAVE_TK

async def produce_save_tk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ans = update.message.text.strip().lower()
    save_tk = ans in ("yes","y","да","+")
    db = db_session()
    try:
        maybe_new_components = None
        if save_tk:
            used = context.user_data["prod_used_raw"]
            total_in = sum(q for _, q in used.values())
            if total_in > 0:
                maybe_new_components = [(cat, (qty/total_in)*100.0) for cat, (_, qty) in used.items()]

        batch = services.produce_batch(
            db=db,
            product_code=context.user_data["prod_product"],
            barrel_code=context.user_data["prod_barrel"],
            target_mass_kg=context.user_data["prod_target_mass"],
            theoretical_yield_pct=context.user_data["prod_ty"],
            used_raw=context.user_data["prod_used_raw"],
            actual_mass_kg=context.user_data["prod_fact_mass"],
            maybe_new_recipe_components=maybe_new_components,
            save_new_recipe_draft=save_tk
        )
        out = [
            f"Замес проведён. Партия бочки id={batch.id}",
            f"Цель: {batch.target_mass_kg} кг; Факт: {batch.actual_mass_kg} кг; План.вход: {batch.planned_input_kg} кг; "
            f"Вых.%: {batch.actual_mass_kg / (batch.planned_input_kg * (batch.theoretical_yield_pct/100.0)) * 100.0:.6f}",
        ]
        if save_tk:
            out.append("Новая ТК сохранена как Черновик. Владелец может утвердить через /tk_drafts.")
        await update.message.reply_text("\n".join(out))
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")
    finally:
        db.close()
    return ConversationHandler.END

# TK drafts (owner)
async def tk_drafts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user and OWNER_TELEGRAM_ID and update.effective_user.id != OWNER_TELEGRAM_ID:
        await update.message.reply_text("Недостаточно прав.")
        return
    db = db_session()
    try:
        drafts = services.list_recipes(db, status=RecipeStatus.draft)
        if not drafts:
            await update.message.reply_text("Черновиков ТК нет.")
            return
        lines = []
        for r in drafts:
            comps = ", ".join([f"{rc.category.name}:{rc.percent:g}%" for rc in r.components])
            lines.append(f"id={r.id} | {r.product.name} | вых:{r.theoretical_yield_pct:g}% | [{comps}]")
        lines.append("\nЧтобы активировать: отправьте /tk_activate <id>")
        await update.message.reply_text("Черновики ТК:\n" + "\n".join(lines))
    finally:
        db.close()

async def tk_activate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user and OWNER_TELEGRAM_ID and update.effective_user.id != OWNER_TELEGRAM_ID:
        await update.message.reply_text("Недостаточно прав.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Использование: /tk_activate <id>")
        return
    try:
        rid = int(args[0])
    except:
        await update.message.reply_text("id должен быть числом.")
        return
    db = db_session()
    try:
        services.activate_recipe(db, rid)
        await update.message.reply_text(f"ТК {rid} активирована. Прежние активные для этого полуфабриката — архивированы.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")
    finally:
        db.close()

def build_application():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    # Category
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("category_add", category_add)],
        states={ CAT_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, category_add_name)] },
        fallbacks=[],
    ))
    app.add_handler(CommandHandler("category_list", category_list))

    # SKU
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("sku_add", sku_add)],
        states={
            SKU_ADD_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, sku_add_type)],
            SKU_ADD_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, sku_add_code)],
            SKU_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, sku_add_name)],
            SKU_ADD_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, sku_add_category)],
            SKU_ADD_PACK_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sku_add_pack_weight)],
        },
        fallbacks=[],
    ))
    app.add_handler(CommandHandler("sku_list", sku_list))

    # Recipes
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("recipe_new", recipe_new)],
        states={
            RECIPE_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, recipe_product)],
            RECIPE_TYIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, recipe_yield)],
            RECIPE_COMPONENTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, recipe_components)],
        },
        fallbacks=[],
    ))
    app.add_handler(CommandHandler("recipe_list", recipe_list))
    app.add_handler(CommandHandler("tk_drafts", tk_drafts))
    app.add_handler(CommandHandler("tk_activate", tk_activate))

    # Produce
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("produce", produce)],
        states={
            PRODUCE_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, produce_product)],
            PRODUCE_BARREL: [MessageHandler(filters.TEXT & ~filters.COMMAND, produce_barrel)],
            PRODUCE_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, produce_target)],
            PRODUCE_FACT_COMPONENTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, produce_fact_components)],
            PRODUCE_FACT_MASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, produce_fact_mass)],
            PRODUCE_SAVE_TK: [MessageHandler(filters.TEXT & ~filters.COMMAND, produce_save_tk)],
        },
        fallbacks=[],
    ))

    return app
