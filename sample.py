import pandas as pd
import os

os.makedirs('data/labeled', exist_ok=True)

dfs = []
for f in ['zhihu', 'reddit', 'weibo', 'xhs']:
    df = pd.read_csv('data/cleaned/' + f + '_cleaned.csv')
    if 'source' not in df.columns:
        df['source'] = f
    if 'query_type' not in df.columns:
        df['query_type'] = 'version'
    dfs.append(df)

all_df = pd.concat(dfs, ignore_index=True)

weights = {'zhihu': 20, 'reddit': 30, 'xhs': 30, 'hackernews': 10, 'weibo': 10}
samples = []
for source, n in weights.items():
    df_s = all_df[all_df['source'] == source]
    samples.append(df_s.sample(min(len(df_s), n), random_state=42))
sample = pd.concat(samples).reset_index(drop=True)

output = sample[['source', 'query_type', 'content']].copy()
output['sentiment'] = ''
output['funnel_stage'] = ''
output['scenario'] = ''
output['feedback_type'] = ''

output.to_csv('data/labeled/manual_sample_100.csv', index=True, index_label='id', encoding='utf-8-sig')
print('已生成', len(output), '条')
print(output['source'].value_counts())
