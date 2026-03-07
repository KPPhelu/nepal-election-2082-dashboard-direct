# dashboard_streamlit.py

import streamlit as st
import pandas as pd
import plotly.express as px
from election_2082 import get_all_live_results
import os
import time
from datetime import datetime
import pytz # Import this at the top

# Set page config
st.set_page_config(page_title="Election 2082 Dashboard", layout="wide")

st.title("🗳️ Election 2082 Live Dashboard (प्रत्यक्ष)")
st.write("(Source: https://www.onlinekhabar.com/)")

def get_time_info(filepath):
    if os.path.exists(filepath):
        # 1. Get the file's modification time (UTC)
        mtime = os.path.getmtime(filepath)
        utc_dt = datetime.fromtimestamp(mtime, tz=pytz.utc)

        # 2. Convert to Nepal Time (+5:45)
        npt_tz = pytz.timezone('Asia/Kathmandu')
        last_updated_npt = utc_dt.astimezone(npt_tz)

        # 3. Get current time in Nepal for "Time Ago" calculation
        now_npt = datetime.now(npt_tz)
        diff = now_npt - last_updated_npt

        # 4. Format the "Time Ago" string
        total_seconds = int(diff.total_seconds())
        if total_seconds < 60:
            time_ago = "just now"
        else:
            hours, remainder = divmod(total_seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            time_ago = f"{hours}h {minutes}m ago" if hours > 0 else f"{minutes}m ago"

        return last_updated_npt.strftime("%Y-%m-%d %I:%M %p"), time_ago

    return "Never", "N/A"

# --- Helper to load data safely ---
def load_data(file):
    try:
        return pd.read_csv(file, encoding='utf-8-sig')
    except FileNotFoundError:
        return None

# --- Helper to load data with fallback ---
def load_data_with_fallback(primary_file, backup_file):
    """Try to load primary file, fallback to backup if missing/empty."""
    try:
        if os.path.exists(primary_file) and os.path.getsize(primary_file) > 0:
            return pd.read_csv(primary_file, encoding='utf-8-sig')
        elif os.path.exists(backup_file):
            st.warning(f"⚠️ {primary_file} not found. Loading backup data...")
            return pd.read_csv(backup_file, encoding='utf-8-sig')
    except Exception as e:
        st.error(f"Error loading {primary_file}: {e}")
    return None

# # Function to fix the status logic
def fix_election_status(df, df_voters):
    if df is None or df_voters is None:
        return df

    # 1. Convert votes to integers for calculation
    df['votes_int'] = df['votes'].apply(lambda x: int(str(x).replace(',', '')) if pd.notnull(x) else 0)

    # 2. Map 'Total Casted Votes' from df_voters to df_live
    # Ensure the keys match (using 'ID' or 'Constituency' depending on your CSV headers)
    casted_map = df_voters.set_index('Constituency')['Total Casted Votes'].to_dict()

    def apply_logic(group):
        # Sort by votes descending to get 1st and 2nd place
        group = group.sort_values('votes_int', ascending=False)

        v1 = group.iloc[0]['votes_int']
        v2 = group.iloc[1]['votes_int'] if len(group) > 1 else 0
        margin = v1 - v2

        # Calculate Remaining Votes
        cid = group.iloc[0]['ID']
        total_casted = casted_map.get(cid, 0)
        total_counted_so_far = group['votes_int'].sum()
        remaining = max(0, total_casted - total_counted_so_far)

        # Logic for the top candidate
        leader_status = group.iloc[0]['Status']

        if leader_status == "Winner":
            new_status = "Winner"
        elif margin > remaining and total_counted_so_far > 0:
            new_status = "Probable Win"
        elif "अग्रता" in str(leader_status) or leader_status == "Leading":
            new_status = "Leading"
        elif "सुरु हुन बाँकी" in str(leader_status) or leader_status == "Not Started":
            new_status = "Not Started"
        else:
            new_status = "Ongoing"

        # Apply: Only the leader gets the status, others get "-"
        group['Status'] = "-"
        group.iloc[0, group.columns.get_loc('Status')] = new_status
        return group

    # Apply the logic per constituency
    df = df.groupby('ID', group_keys=False).apply(apply_logic)
    return df.drop(columns=['votes_int'])


# Calculate Vote % for each candidate
def calculate_vote_share(df_live, df_voters):
    casted_map = df_voters.set_index('Constituency')['Total Casted Votes'].to_dict()
    df_live['votes_int'] = df_live['votes'].apply(lambda x: int(str(x).replace(',', '')) if pd.notnull(x) else 0)

    def get_share(row):
        total = casted_map.get(row['ID'], 0)
        return round((row['votes_int'] / total) * 100, 2) if total > 0 else 0

    df_live['Vote % Share'] = df_live.apply(get_share, axis=1)
    return df_live

# Load your scraped data
df_voters = load_data("election_2082_voter_stats.csv")
df_parties = load_data("election_2082_party_list.csv")
# df_live = load_data("live_election_results_2082.csv")
df_live = load_data_with_fallback("live_election_results_2082.csv", "live_election_results_2082_backup.csv")
df_translate = load_data("translation_name_map.csv")

# Apply the fix
if df_live is not None:
    df_live = fix_election_status(df_live, df_voters)
    df_live = calculate_vote_share(df_live, df_voters)

# Create Tabs for different views
tab1, tab2, tab3 = st.tabs(["📡 Live Count", "📊 Voter Stats", "🚩 Party List"])

with tab1:
    if df_live is not None:
        # --- DEFINE GLOBAL COLOR MAP FIRST ---
        # Get all unique parties from the live data
        all_parties = sorted(df_live['party'].unique())
        # Create a consistent color mapping for the entire dashboard
        color_map = {p: px.colors.qualitative.Plotly[i % 10] for i, p in enumerate(all_parties)}


        # 1. Header with Refresh Button
        col_t, col_b = st.columns([3, 1])

        with col_t:
            st.subheader("📡 Live Election Count")
            update_time, time_ago = get_time_info("live_election_results_2082.csv")
            st.caption(f"Last updated: **{update_time}** ({time_ago})")

        with col_b:
            if st.button("🔄 Refresh Data"):
                progress_bar = st.progress(0)
                status_text = st.empty()

                # Run the 5-worker scraper
                if get_all_live_results(progress_bar, status_text):
                    status_text.empty()  # Remove "Scraping 165/165..."
                    progress_bar.empty()  # Remove progress bar
                    st.success("Data Updated Successfully!")
                    time.sleep(1)
                    st.rerun()  # This reloads the CSV into your charts

        st.divider()

        # --- 2. Election Progress Overview ---
        st.subheader("📊 Election Progress Overview")

        # Identify state per constituency
        status_summary = df_live.groupby('ID')['Status'].apply(list).reset_index()


        def get_state(s_list):
            if "Winner" in s_list:
                return "Finished"
            if "Probable Win" in s_list:
                return "Probable"
            if "Leading" in s_list:  # Change "Ongoing" to "Leading" to match charts
                return "Ongoing"
            return "Not Started"


        status_summary['State'] = status_summary['Status'].apply(get_state)
        counts = status_summary['State'].value_counts()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("✅ Counting Finished", counts.get("Finished", 0))
        m2.metric("✨ Probable Wins", counts.get("Probable", 0))
        m3.metric("⏳ Counting Ongoing", counts.get("Ongoing", 0))
        m4.metric("⚪ Not Started", counts.get("Not Started", 0))

        st.divider()

        # --- 3. PIE CHART National Seat Share Pie Chart ---
        st.subheader("🎯 Overall Seat Share (Confirmed + Probable)")

        # Filter for both Winners and Probable Wins
        df_combined = df_live[df_live['Status'].isin(["Winner", "Probable Win"])]

        if not df_combined.empty:
            # Count seats per party
            seat_counts = df_combined['party'].value_counts().reset_index()
            seat_counts.columns = ['Party', 'Seats']

            # Create Pie Chart
            fig_pie = px.pie(
                seat_counts,
                values='Seats',
                names='Party',
                title="Distribution of Won & Probable Seats",
                color='Party',
                color_discrete_map=color_map, # Uses your existing color map
                hole=0.4 # Makes it a Donut Chart for better readability
            )

            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            fig_pie.update_layout(margin=dict(l=20, r=20, t=40, b=20))

            # Display the Pie Chart
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No confirmed or probable wins recorded yet to display seat share.")

        st.divider()


        # --- 4. NATIONAL TALLY CHARTS (Bar Charts)  (3 Columns) ---
        st.subheader("🏁 Current Tally Summary")

        # # Create a shared color map for parties
        # all_parties = sorted(df_live['party'].unique())
        # color_map = {p: px.colors.qualitative.Plotly[i % 10] for i, p in enumerate(all_parties)}


        def plot_tally_no_legend(df_filter, title):
            if not df_filter.empty:
                tally = df_filter['party'].value_counts().reset_index()
                tally.columns = ['Party', 'Seats']

                fig = px.bar(tally, x='Party', y='Seats', title=title,
                             color='Party', color_discrete_map=color_map, text_auto=True)

                # Hide legend on ALL charts to maintain equal width
                fig.update_layout(
                    xaxis={'categoryorder': 'total descending', 'title': ''},
                    showlegend=False,
                    margin=dict(l=10, r=10, t=40, b=20)
                )
                # UPDATED: Use width="stretch" instead of use_container_width=True
                st.plotly_chart(fig, width="stretch")
            else:
                st.info(f"No {title.lower()} data yet.")


        # Row 1: The 3 Charts
        c1, c2, c3 = st.columns(3)
        with c1:
            plot_tally_no_legend(df_live[df_live['Status'] == "Winner"], "🏆 Confirmed Wins")
        with c2:
            plot_tally_no_legend(df_live[df_live['Status'] == "Probable Win"], "✨ Probable Wins")
        with c3:
            plot_tally_no_legend(df_live[df_live['Status'] == "Leading"], "📈 Current Leading")

        # Row 2: Shared Legend below
        # 1. Identify which parties are actually visible in the 3 status categories
        active_statuses = ["Winner", "Probable Win", "Leading"]
        active_df = df_live[df_live['Status'].isin(active_statuses)]

        if not active_df.empty:
            # Count total seats per party across all 3 statuses
            tally_counts = active_df['party'].value_counts().reset_index()
            tally_counts.columns = ['party', 'total_seats']

            # Sort by seat count (descending) so the legend matches the chart order
            tally_counts = tally_counts.sort_values('total_seats', ascending=False)

            # --- 2. Build the Legend Row ---
            st.write("---")
            legend_html = '<div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 25px;">'

            for _, row in tally_counts.iterrows():
                party = row['party']
                count = row['total_seats']
                color = color_map.get(party, "#000")

                # Adding (Count) next to the name for better context
                legend_html += (
                    f'<div style="display: flex; align-items: center; font-size: 0.9rem; white-space: nowrap;">'
                    f'<div style="width: 14px; height: 14px; background-color: {color}; margin-right: 8px; border-radius: 2px;"></div>'
                    f'<b>{party}</b> <span style="margin-left:4px; color:gray;">({count})</span></div>'
                )

            legend_html += '</div>'
            st.markdown(legend_html, unsafe_allow_html=True)
        else:
            st.write("---")
            st.caption("No active leads or wins to display in the legend yet.")

        # --- 5. Unified Search Implementation ---
        st.divider()
        st.subheader("🔍 Search Candidate or Constituency")

        # Load the static translation file locally for the search tool
        # df_translate = load_data("translation_name_map.csv")

        if df_live is not None and df_translate is not None:
            # 1. Create a local copy for searching to avoid affecting main df_live
            # Merge English names onto the live data for the search labels
            search_master = pd.merge(
                df_live,
                df_translate[['ID', 'name', 'name_english']],
                on=['ID', 'name'],
                how='left'
            )
            search_master['name_english'] = search_master['name_english'].fillna(search_master['name'])

            # 2. Generate the "English | Nepali (Constituency)" search strings
            search_master['search_label'] = (
                    search_master['name_english'] + " | " +
                    search_master['name'] + " (" +
                    search_master['ID'] + ")"
            )

            # 3. Search Bar with type-to-filter
            selected_option = st.selectbox(
                "Type to search (e.g., 'Balen', 'काठमाडौं', or 'Kathmandu'):",
                options=[""] + sorted(search_master['search_label'].unique().tolist()),
                index=0,
                placeholder="Search here..."
            )

            if selected_option:
                # 1. Get the ID of the selected constituency from our search master
                selected_row = search_master[search_master['search_label'] == selected_option].iloc[0]
                selected_id = selected_row['ID']

                # 4. Display Results (Filter from original df_live to keep your existing logic intact)
                # st.info(f"📍 Showing Detailed Results for: **{selected_id}**")

                # Filter original df_live by the selected ID
                con_results = df_live[df_live['ID'] == selected_id].copy()

                # Ensure votes are treated as numeric for sorting
                con_results['votes_int'] = con_results['votes'].apply(
                    lambda x: int(str(x).replace(',', '')) if pd.notnull(x) else 0
                )
                con_results = con_results.sort_values('votes_int', ascending=False)

                # --- Show results inside an Expander ---
                # The label shows the Constituency ID/Name
                # Get the leader (top row)
                leader = con_results.iloc[0]
                total_counted_so_far = con_results['votes_int'].sum()
                # 3. Get total casted from voter stats (mapped by 'Constituency' key in df_voters)
                # Check if df_voters exists and find matching row for the selected_id
                voter_row = df_voters[df_voters['Constituency'] == selected_id]
                total_casted = int(voter_row['Total Casted Votes'].iloc[0]) if not voter_row.empty else 0
                # Calculations
                remaining = max(0, total_casted - total_counted_so_far)
                progress_percent = (total_counted_so_far / total_casted * 100) if total_casted > 0 else 0
                nepali_con_name = leader['Constituency']
                # 4. Construct the Unified Label
                label = (f"📍 {nepali_con_name} — {leader['name']} ({leader['party']}) | "
                         f"{progress_percent:.1f}% Counted | "
                         f"Counted: {total_counted_so_far:,} | "
                         f"Remaining: {remaining:,}")

                # nepali_con_name = df_live[df_live['ID'] == selected_id]['Constituency'].iloc[0]
                with st.expander(label, expanded=True):
                    st.table(con_results[['name', 'party', 'votes', 'Vote % Share', 'Status']])
                #
                # # Show the table as requested (Detailed Tally style)
                # st.table(con_results[['name', 'party', 'votes', 'Vote % Share', 'Status']])
        else:
            st.warning("Search unavailable: Ensure 'translation_name_map.csv' is in your repository.")



        # --- 6. Detailed Tally Tables (4 Parts) ---
        st.write("### 📋 Detailed Constituency Tables")

        # Define columns for the summary and the full candidate list
        summary_cols = ["name", "party", "votes", "Vote % Share", "Status"]


        def show_constituency_expanders(filtered_df, section_title, default_expanded=False):
            """Helper to create nested expanders with unified status labels"""

            # 1. Calculate count of unique IDs for the section title
            unique_ids = filtered_df['ID'].unique() if not filtered_df.empty else []
            count = len(unique_ids)
            full_title = f"{section_title} ({count})"

            with st.expander(full_title, expanded=default_expanded):
                if count > 0:
                    # Sort constituencies alphabetically (A-Z)
                    sorted_ids = filtered_df.sort_values("Constituency")['ID'].unique()

                    for cid in sorted_ids:
                        # Filter data for this specific constituency
                        c_df = df_live[df_live['ID'] == cid].copy()

                        # Ensure numerical sorting for the table
                        c_df['votes_int'] = c_df['votes'].apply(
                            lambda x: int(str(x).replace(',', '')) if pd.notnull(x) else 0)
                        c_df = c_df.sort_values("votes_int", ascending=False)

                        leader = c_df.iloc[0]
                        c_name = leader['Constituency']

                        # Calculation Logic
                        total_casted = df_voters.set_index('Constituency')['Total Casted Votes'].get(cid, 0)
                        total_counted_so_far = c_df['votes_int'].sum()
                        remaining = max(0, total_casted - total_counted_so_far)
                        progress_percent = (total_counted_so_far / total_casted * 100) if total_casted > 0 else 0

                        # Unified Label: Counted % | Counted Votes | Remaining Votes
                        label = (f"📍 {c_name} — {leader['name']} ({leader['party']}) | "
                                 f"{progress_percent:.1f}% Counted | "
                                 f"Counted: {total_counted_so_far:,} | "
                                 f"Remaining: {remaining:,}")

                        # with st.container():
                        with st.expander(label):
                            # Display the full candidate list in descending order
                            st.dataframe(
                                c_df[summary_cols],
                                width="stretch",
                                hide_index=True
                            )
                else:
                    st.info(f"No constituencies in this category yet.")


        # --- Call the simplified function ---
        show_constituency_expanders(df_live[df_live["Status"] == "Winner"], "✅ Counting Finished (Winner Declared)",
                                    )
        show_constituency_expanders(df_live[df_live["Status"] == "Probable Win"],
                                    "✨ Probable Wins (Statistically Decided)")
        show_constituency_expanders(df_live[df_live["Status"] == "Leading"], "⏳ Counting Ongoing (Active Leads)")

        # 4. Not Started (Simplified list)
        active_statuses = ["Winner", "Probable Win", "Leading"]
        # Get IDs that DO have an active status
        started_ids = df_live[df_live['Status'].isin(active_statuses)]['ID'].unique()
        # Filter df_live for IDs NOT in the started list
        not_started_df = df_live[~df_live['ID'].isin(started_ids)]
        count_not_started = not_started_df['ID'].nunique() if not not_started_df.empty else 0

        with st.expander(f"⚪ Not Started (Waiting to Count) - {count_not_started}"):
            if not not_started_df.empty:
                unique_ns = sorted(not_started_df['Constituency'].unique())
                st.info("The following areas have not reported any votes yet:")
                st.write(", ".join(unique_ns))
            else:
                st.success("All constituencies have started reporting votes!")

# --- Tab 2: Voter Statistics ---
with tab2:
    if df_voters is not None:
        st.header("Voter Turnout & Statistics")

        # Summary Metrics
        total_voters = df_voters["Total Votes"].sum()
        total_casted = df_voters["Total Casted Votes"].sum()
        avg_turnout = df_voters["Vote %"].mean()

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Eligible Voters", f"{total_voters:,}")
        m2.metric("Total Votes Casted", f"{total_casted:,}")
        m3.metric("Average Turnout %", f"{avg_turnout:.2f}%")

        st.divider()

        # Visualizations
        c1, c2 = st.columns(2)
        with c1:
            # Top 10 Turnout
            high_turnout = df_voters.nlargest(10, "Vote %")
            fig_high = px.bar(high_turnout, x="Constituency", y="Vote %",
                              title="🚀 Highest Turnout Constituencies", color="Vote %")
            st.plotly_chart(fig_high, use_container_width=True)

        with c2:
            # Bottom 10 Turnout
            low_turnout = df_voters.nsmallest(10, "Vote %")
            fig_low = px.bar(low_turnout, x="Constituency", y="Vote %",
                             title="📉 Lowest Turnout Constituencies", color="Vote %")
            st.plotly_chart(fig_low, use_container_width=True)

        st.write("### 🔍 Full Voter Data Search")
        search = st.text_input("Filter by Constituency Name")
        if search:
            st.dataframe(df_voters[df_voters['Constituency'].str.contains(search, case=False)],
                         use_container_width=True)
        else:
            st.dataframe(df_voters, use_container_width=True)

# --- Tab 3: Party List ---
with tab3:
    if df_parties is not None:
        st.header("🚩 Participating Political Parties")

        # Display as a grid of cards
        cols = st.columns(4)
        for idx, row in df_parties.iterrows():
            with cols[idx % 4]:
                st.image(row['Logo URL'], width=80)
                st.caption(row['Party Name'])
    else:
        st.info("Party data not found. Run the scraper to generate the CSV.")