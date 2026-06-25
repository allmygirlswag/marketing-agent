from flask import Flask, render_template, request, jsonify
import csv

app = Flask(__name__)

def load_campaigns():
    """Загружает данные из CSV"""
    campaigns = []
    with open('data/campaigns.csv', 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            campaigns.append({
                'campaign': row['campaign'],
                'platform': row['platform'],
                'budget': float(row['budget']),
                'spend': float(row['spend']),
                'impressions': float(row['impressions']),
                'clicks': float(row['clicks']),
                'conversions': float(row['conversions'])
            })
    return campaigns

def calculate_metrics(campaigns):
    """Рассчитывает CPC, CPA, CPM, CTR, Conversion Rate"""
    for c in campaigns:
        # CPC - стоимость клика
        c['cpc'] = round(c['spend'] / c['clicks'], 2) if c['clicks'] > 0 else 0
        
        # CPA - стоимость конверсии
        c['cpa'] = round(c['spend'] / c['conversions'], 2) if c['conversions'] > 0 else 0
        
        # CPM - стоимость 1000 показов
        c['cpm'] = round((c['spend'] / c['impressions']) * 1000, 2) if c['impressions'] > 0 else 0
        
        # CTR - кликабельность
        c['ctr'] = round((c['clicks'] / c['impressions']) * 100, 2) if c['impressions'] > 0 else 0
        
        # Conversion Rate - конверсия
        c['conversion_rate'] = round((c['conversions'] / c['clicks']) * 100, 2) if c['clicks'] > 0 else 0
    
    return campaigns

def optimize_budget(campaigns):
    """
    Логика AI-агента по перераспределению бюджета
    Общий бюджет остается неизменным!
    """
    # Копируем данные, чтобы не менять оригинал
    campaigns_copy = []
    for c in campaigns:
        campaigns_copy.append({
            'campaign': c['campaign'],
            'platform': c['platform'],
            'budget': c['budget'],
            'spend': c['spend'],
            'impressions': c['impressions'],
            'clicks': c['clicks'],
            'conversions': c['conversions'],
            'cpc': c['cpc'],
            'cpa': c['cpa'],
            'cpm': c['cpm'],
            'ctr': c['ctr'],
            'conversion_rate': c['conversion_rate']
        })
    
    # Сортируем кампании по эффективности (conversion_rate)
    # Чем выше conversion_rate, тем эффективнее кампания
    sorted_campaigns = sorted(campaigns_copy, key=lambda x: x['conversion_rate'], reverse=True)
    
    # Определяем, сколько кампаний будем "награждать" и "наказывать"
    # Если кампаний мало (≤ 4), то берем 1 лучшую и 1 худшую
    if len(sorted_campaigns) <= 4:
        num_best = 1
        num_worst = 1
    else:
        num_best = max(1, len(sorted_campaigns) // 3)  # 1/3 лучших
        num_worst = max(1, len(sorted_campaigns) // 3)  # 1/3 худших
    
    # Забираем деньги у худших кампаний (последние в списке)
    worst_campaigns = sorted_campaigns[-num_worst:]
    total_taken = 0
    taken_details = []
    
    for c in worst_campaigns:
        # Забираем 20% бюджета (но не более 50% и не менее 1000 ₽)
        take_percent = 0.20
        take_amount = c['budget'] * take_percent
        
        # Ограничиваем, чтобы не уйти в минус
        if take_amount > c['budget'] * 0.5:
            take_amount = c['budget'] * 0.5
        if take_amount < 1000:
            take_amount = min(1000, c['budget'] * 0.5)
        
        c['budget'] = round(c['budget'] - take_amount, 2)
        total_taken += take_amount
        taken_details.append({
            'campaign': c['campaign'],
            'taken': round(take_amount, 2),
            'new_budget': c['budget']
        })
        c['action'] = f'📉 -{round(take_amount, 2)} ₽ (перераспределено)'
    
    # Отдаем забранные деньги лучшим кампаниям (первые в списке)
    best_campaigns = sorted_campaigns[:num_best]
    bonus_per_campaign = total_taken / len(best_campaigns) if best_campaigns else 0
    
    for c in best_campaigns:
        # Проверяем, не является ли кампания одновременно и лучшей и худшей
        # (такое возможно при очень маленьком количестве кампаний)
        if c in worst_campaigns:
            continue
            
        c['budget'] = round(c['budget'] + bonus_per_campaign, 2)
        if c.get('action'):
            c['action'] += f' +{round(bonus_per_campaign, 2)} ₽'
        else:
            c['action'] = f'📈 +{round(bonus_per_campaign, 2)} ₽ (лучшая конверсия)'
    
    # Если остались нераспределенные деньги (из-за округления)
    remaining = total_taken - (bonus_per_campaign * len(best_campaigns))
    if remaining > 0 and best_campaigns:
        best_campaigns[0]['budget'] = round(best_campaigns[0]['budget'] + remaining, 2)
        best_campaigns[0]['action'] += f' +{round(remaining, 2)} ₽ (округление)'
    
    # Для остальных кампаний - без изменений
    for c in sorted_campaigns:
        if 'action' not in c or not c['action']:
            c['action'] = '✅ Без изменений'
    
    # Возвращаем все кампании в исходном порядке (не сортированном)
    campaign_names = [c['campaign'] for c in campaigns]
    result = []
    for name in campaign_names:
        for c in sorted_campaigns:
            if c['campaign'] == name:
                result.append(c)
                break
    
    return result

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/api/campaigns', methods=['GET'])
def get_campaigns():
    """Возвращает данные кампаний с рассчитанными метриками"""
    campaigns = load_campaigns()
    campaigns = calculate_metrics(campaigns)
    return jsonify(campaigns)

@app.route('/api/optimize', methods=['POST'])
def optimize():
    """
    Запускает агента-оптимизатора (перераспределение бюджета)
    Принимает данные кампаний, возвращает оптимизированные
    """
    data = request.get_json()
    campaigns = data['campaigns']
    
    # Рассчитываем метрики для входящих данных
    campaigns = calculate_metrics(campaigns)
    
    # Сохраняем старые бюджеты для статистики
    old_budgets = {c['campaign']: c['budget'] for c in campaigns}
    old_total = sum(c['budget'] for c in campaigns)
    
    # Запускаем оптимизацию (перераспределение)
    optimized_campaigns = optimize_budget(campaigns)
    
    # Считаем статистику
    total_budget = sum(c['budget'] for c in optimized_campaigns)
    
    # Считаем сколько денег перераспределено
    total_moved = 0
    increased = 0
    decreased = 0
    
    for c in optimized_campaigns:
        old = old_budgets.get(c['campaign'], c['budget'])
        diff = abs(c['budget'] - old)
        if diff > 0:
            total_moved += diff
            if c['budget'] > old:
                increased += 1
            elif c['budget'] < old:
                decreased += 1
    
    # Округляем до 2 знаков
    total_moved = round(total_moved, 2)
    
    response = {
        'campaigns': optimized_campaigns,
        'summary': {
            'total_budget': round(total_budget, 2),
            'budget_change': round(total_budget - old_total, 2),
            'campaigns_optimized': sum(1 for c in optimized_campaigns if c['action'] != '✅ Без изменений'),
            'budget_moved': total_moved,
            'increased': increased,
            'decreased': decreased
        }
    }
    
    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True, port=5000)