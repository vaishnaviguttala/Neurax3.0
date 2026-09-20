import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

st.set_page_config(page_title='UrbanPulse', page_icon='🚦', layout='wide')
DATA = Path(__file__).parent / 'data'

st.markdown('''<style>.block-container{padding-top:1.2rem}.hero{padding:1rem 1.2rem;border-radius:16px;background:linear-gradient(135deg,#102a43,#1d4e89);color:white}.report{border:1px solid #f59e0b;padding:12px;border-radius:12px}</style>''', unsafe_allow_html=True)

@st.cache_data
def load_data():
    traffic = pd.read_csv(DATA/'traffic_train.csv', parse_dates=['timestamp'])
    network = pd.read_csv(DATA/'network.csv')
    incidents = pd.read_csv(DATA/'incidents_train.csv', parse_dates=['start_time','end_time'])
    plans = pd.read_csv(DATA/'planning_candidates.csv')
    return traffic, network, incidents, plans

traffic, network, incidents, plans = load_data()
traffic = traffic.merge(network, on=['segment_id','source_node','target_node'], how='left', suffixes=('','_network'))
traffic['status'] = pd.cut(traffic['congestion_index'], [-.01,.30,.60,1.01], labels=['Free flow','Moderate','Severe'])
traffic['utilization_pct'] = (traffic['flow_vph'] / traffic['capacity_vph'].replace(0,np.nan)*100).clip(0,200)
traffic['risk_score'] = (traffic['congestion_index']*60 + traffic['occupancy_pct'].clip(0,100)*.25 + traffic['queue_length_veh'].clip(0,200)*.15).clip(0,100)

# -------------------- LOGIN / HOME --------------------
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'role' not in st.session_state:
    st.session_state.role = None

if not st.session_state.authenticated:
    st.markdown('<div class="hero"><h1>🚦 UrbanPulse</h1><p>Welcome to intelligent, safer urban mobility</p></div>', unsafe_allow_html=True)
    st.markdown('## Welcome!')
    st.write('Choose your access type and sign in to open your personalized dashboard.')
    with st.form('login_form', clear_on_submit=False):
        login_role = st.selectbox('Login as', ['Public user', 'Admin / Official'])
        username = st.text_input('Username')
        password = st.text_input('Password', type='password')
        submitted = st.form_submit_button('🔐 Login', use_container_width=True)
        if submitted:
            valid = (login_role == 'Public user' and username == 'user' and password == 'user123') or (login_role == 'Admin / Official' and username == 'admin' and password == 'admin123')
            if valid:
                st.session_state.authenticated = True
                st.session_state.role = login_role
                st.rerun()
            else:
                st.error('Invalid credentials. Use the demo credentials shown below.')
    st.info('Demo login — Public user: user / user123 | Admin / Official: admin / admin123')
    st.caption('Prototype only: replace demo login with secure authentication before deployment.')
    st.stop()

role = st.session_state.role
st.markdown('<div class="hero"><h1>🚦 UrbanPulse</h1><p>Public mobility assistance and authorized traffic-control intelligence</p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.header('👤 Logged in')
    st.success(role)
    if st.button('🚪 Logout', use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.role = None
        st.rerun()
    st.divider()
    min_date, max_date = traffic.timestamp.min().date(), traffic.timestamp.max().date()
    selected_date = st.date_input('Analysis date', min_value=min_date, max_value=max_date, value=min_date)
    segment_options = ['All segments'] + sorted(traffic.segment_id.dropna().unique().tolist())
    selected_segment = st.selectbox('Road segment', segment_options)
    severity_filter = st.multiselect('Congestion levels', ['Free flow','Moderate','Severe'], default=['Free flow','Moderate','Severe'])
    st.info('Use the visible sections to access mobility services.')

view = traffic[traffic.timestamp.dt.date == selected_date].copy()
if selected_segment != 'All segments': view = view[view.segment_id == selected_segment]
view = view[view.status.astype(str).isin(severity_filter)]

k1,k2,k3,k4 = st.columns(4)
k1.metric('Road records', f'{len(view):,}')
k2.metric('Average speed', f'{view.speed_kmh.mean():.1f} km/h' if len(view) else '—')
k3.metric('Average congestion', f'{view.congestion_index.mean():.2f}' if len(view) else '—')
k4.metric('Active incidents', f'{len(incidents[incidents.segment_id.isin(view.segment_id.unique())]):,}')

labels = ['📊 Overview','🚨 Accident detection','🅿️ Smart parking','🔎 Bottlenecks & reports','🗺️ Route assistant','📋 Recommendations']
if role == 'Admin / Official': labels.insert(5, '🚥 Signal coordination')
tabs = st.tabs(labels)

with tabs[0]:
    st.subheader('Network overview')
    if len(view):
        st.line_chart(view.groupby('timestamp',as_index=True).congestion_index.mean(), height=280)
        cols=['timestamp','segment_id','speed_kmh','flow_vph','occupancy_pct','delay_min','queue_length_veh','congestion_index','status']
        st.dataframe(view[cols].sort_values('congestion_index',ascending=False).head(150), use_container_width=True, hide_index=True)
    else: st.warning('No records match the selected filters.')

with tabs[1]:
    st.subheader('Automatic accident / abnormal-event detection')
    st.caption('Prototype screening logic. Real deployment requires validated CCTV, IoT, emergency-service and human verification workflows.')
    accidents = view[(view.speed_kmh < view.free_flow_speed_kmh*0.45) & ((view.occupancy_pct>70) | (view.queue_length_veh>20))] if len(view) else view
    known = incidents[incidents.segment_id.isin(view.segment_id.unique())]
    a,b,c=st.columns(3); a.metric('Potential events',len(accidents)); b.metric('Known incidents',len(known)); c.metric('High severity',int((known.severity>=2).sum()) if len(known) else 0)
    st.dataframe(accidents[['timestamp','segment_id','speed_kmh','occupancy_pct','queue_length_veh','risk_score']].sort_values('risk_score',ascending=False),use_container_width=True,hide_index=True)
    st.dataframe(known,use_container_width=True,hide_index=True)

with tabs[2]:
    st.subheader('Smart parking')
    zones = pd.DataFrame({'Zone':['P1 - Transit hub','P2 - Market district','P3 - Office corridor','P4 - Residential edge'], 'Capacity':[180,240,320,150], 'Occupied':[142,219,276,74]})
    zones['Available']=zones.Capacity-zones.Occupied; zones['Occupancy %']=(zones.Occupied/zones.Capacity*100).round(1); zones['Status']=np.select([zones['Occupancy %']>=90,zones['Occupancy %']>=75],['Full','Filling fast'],'Available')
    st.dataframe(zones,use_container_width=True,hide_index=True)
    st.success('Choose a zone with available spaces. Live reservation and payment can be integrated later.')

with tabs[3]:
    st.subheader('Bottlenecks: information and public reporting')
    st.caption('Users can view the issue, understand its likely cause, and submit a report for officials.')
    if len(view):
        bottlenecks=view.groupby(['segment_id','road_class','lanes','structural_bottleneck'],as_index=False).agg(avg_congestion=('congestion_index','mean'),avg_delay=('delay_min','mean'),avg_queue=('queue_length_veh','mean'),avg_utilization=('utilization_pct','mean')).sort_values(['avg_congestion','avg_queue'],ascending=False).head(20)
        for _, row in bottlenecks.iterrows():
            severity = 'Severe' if row.avg_congestion >= .60 else 'Moderate' if row.avg_congestion >= .30 else 'Low'
            with st.container(border=True):
                st.markdown(f"**{row.segment_id} — {severity} bottleneck**")
                st.write(f"Average congestion: **{row.avg_congestion:.2f}** | Queue: **{row.avg_queue:.1f} vehicles** | Delay: **{row.avg_delay:.1f} min**")
                st.write(f"Likely infrastructure factor: **{row.structural_bottleneck}**. Suggested action: inspect junction geometry, lane utilization, parking obstruction, signal timing and incident history.")
                if st.button(f'📣 Report {row.segment_id} to officials', key=f'report_{row.segment_id}'):
                    st.session_state['reported'] = row.segment_id
                    st.success(f'Report draft created for {row.segment_id}.')
                if st.session_state.get('reported') == row.segment_id:
                    with st.form(f'form_{row.segment_id}'):
                        reason = st.selectbox('Report category',['Congestion','Road damage','Blocked lane','Unsafe junction','Signal issue','Other'], key=f'cat_{row.segment_id}')
                        details = st.text_area('Additional details', placeholder='Describe what you observed...', key=f'detail_{row.segment_id}')
                        contact = st.text_input('Contact / reference (optional)', key=f'contact_{row.segment_id}')
                        if st.form_submit_button('Submit report'):
                            st.success('Demo report submitted locally. Connect this form to an official civic-ticket API or database for real submission.')
                            st.download_button('Download report', f'Segment: {row.segment_id}\nCategory: {reason}\nDetails: {details}\nContact: {contact}\nTime: {datetime.now()}', file_name=f'{row.segment_id}_report.txt')
    else: st.info('No bottleneck records for this filter.')

with tabs[4]:
    st.subheader('🗺️ Easy and safe route assistant')
    st.write('Ask for a route using plain language. This prototype uses available road records and avoids segments with high congestion.')
    question = st.chat_input('Example: Find the safest route with low congestion')
    if question:
        q = question.lower()
        if 'safe' in q or 'easiest' in q or 'route' in q:
            route_data = traffic.groupby('segment_id',as_index=False).agg(congestion_index=('congestion_index','mean'),speed_kmh=('speed_kmh','mean'),delay_min=('delay_min','mean'),risk_score=('risk_score','mean')).sort_values(['risk_score','congestion_index'])
            st.chat_message('user').write(question)
            st.chat_message('assistant').write('Based on the available prototype data, consider these lower-risk road segments. Confirm live conditions before travelling:')
            st.dataframe(route_data.head(5), use_container_width=True, hide_index=True)
            st.info('For true origin-to-destination routing, connect a road-network routing engine with live traffic, closures, emergency alerts and accessibility preferences.')
        else:
            st.chat_message('assistant').write('Try asking: “Find the safest route” or “Show an easy route with low congestion.”')

route_tab_index = 5 if role == 'Admin / Official' else None
if role == 'Admin / Official':
    with tabs[5]:
        st.subheader('🚥 Predictive traffic signal coordination — Admin only')
        st.warning('Restricted to authorized administrators and traffic officials.')
        if len(view):
            sig=view.groupby('signal_id',as_index=False).agg(congestion=('congestion_index','mean'),queue=('queue_length_veh','mean'),delay=('delay_min','mean'),segments=('segment_id','nunique'))
            sig['priority_score']=(sig.congestion*70+sig.queue.clip(0,100)*.2+sig.delay.clip(0,30)*.33).round(1)
            sig['Suggested plan']=np.select([sig.priority_score>=55,sig.priority_score>=30],['Extend green on congested approach','Coordinate offset / monitor'],default='Normal cycle')
            st.dataframe(sig.sort_values('priority_score',ascending=False),use_container_width=True,hide_index=True)
        else: st.info('No signal data for this filter.')

with tabs[-1]:
    st.subheader('Recommendations')
    if len(view):
        worst=view.sort_values(['congestion_index','queue_length_veh'],ascending=False).iloc[0]
        st.warning(f"Monitor {worst.segment_id}; congestion index is {worst.congestion_index:.2f}.")
        st.write('- Improve junction geometry after a corridor study.\n- Remove lane obstructions and illegal parking.\n- Use adaptive signal control with live detectors.\n- Deploy parking guidance to reduce cruising traffic.\n- Track incident response and clearance time.')
    else: st.info('No recommendations available.')

st.divider()
st.caption('Prototype disclaimer: outputs are simulated decision-support results. Validate with live data, field studies, official workflows and traffic authority approval before deployment.')
