<script>
	import { onMount } from 'svelte';

	let initial = $state([]);
	let rows = $state([]);
	let notes = $state([]);
	let selected = $state(null);
	let note = $state('');
	let error = $state('');
	let busy = $state(false);
	let active = $state('');
	let unit = $state('');

	const groups = $derived.by(() => {
		const seen = new Set();
		for (const r of initial) seen.add(r.cluster_id ?? 'outliers');
		return [...seen];
	});

	async function read(url, options) {
		const response = await fetch(url, options);
		if (!response.ok) throw new Error(`Request failed (${response.status})`);
		return response.json();
	}

	async function load(group = '') {
		busy = true;
		error = '';
		active = group;
		try {
			const payload = await read('/api/records' + (group ? '?cluster=' + encodeURIComponent(group) : ''));
			rows = payload.rows;
		} catch (e) {
			error = e.message;
		} finally {
			busy = false;
		}
	}

	async function start() {
		await load();
		initial = [...rows];
		try {
			const task = await read('/api/task');
			unit = task.contract.unit;
			notes = await read('/api/annotations');
		} catch (e) {
			error = e.message;
		}
	}

	async function save(event) {
		event.preventDefault();
		if (!selected || !note.trim()) return;
		busy = true;
		error = '';
		try {
			await read('/api/annotations', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					record_id: selected.id,
					note: note.trim(),
					start: selected.date,
					end: selected.date
				})
			});
			notes = await read('/api/annotations');
			note = '';
		} catch (e) {
			error = e.message;
		} finally {
			busy = false;
		}
	}

	onMount(() => {
		start();
	});
</script>

<main>
	<header>
		<p>BONSAI / SOURCE EXPLORER</p>
		<h1>Bonsai repository observations</h1>
		<p>User-provided observations. Groups are supplied labels, not inferred similarity clusters.</p>
		<p>{unit}. Rolling repository downloads do not measure unique users or daily downloads.</p>
	</header>

	{#if error}
		<p role="alert">{error}</p>
	{/if}

	{#if busy}
		<p role="status">Loading…</p>
	{/if}

	<section aria-label="Source groups">
		<svg viewBox="0 0 400 100" role="img" aria-label="Group sizes in the full snapshot">
			{#each groups as group, i (group)}
				<circle cx={40 + i * 90} cy="40" r={10 + initial.filter((r) => (r.cluster_id ?? 'outliers') === group).length * 2} fill="#42654c" />
				<text x={40 + i * 90} y="90" text-anchor="middle">{group}</text>
			{/each}
		</svg>

		<nav aria-label="Filter source group">
			{#each groups as group (group)}
				<button aria-pressed={active === group} onclick={() => load(group)}>
					{group} ({initial.filter((r) => (r.cluster_id ?? 'outliers') === group).length})
				</button>
			{/each}
			<button data-testid="clear-filters" onclick={() => load()}>Clear filters</button>
		</nav>
	</section>

	<h2>{rows.length} records shown of {initial.length}</h2>

	{#if !busy && !rows.length}
		<p>No matching records.</p>
	{/if}

	<ul>
		{#each rows as row (row.id)}
			<li data-testid="record-row" data-record-id={row.id}>
				<button onclick={() => selected = row} aria-pressed={selected?.id === row.id}>
					Inspect {row.id}
				</button>
				<span data-testid="record-value">{row.value === null ? 'Missing' : row.value}</span>
				<span>{row.date} / {row.parameter_size} / {row.runtime} / {row.release}</span>
				<a href={row.source_url} target="_blank" rel="noreferrer">Source for {row.id}</a>
			</li>
		{/each}
	</ul>

	<section aria-label="Evidence notes">
		<h2>Annotate a source</h2>
		<p>{selected ? selected.id : 'Select a source record to attach a note.'}</p>
		<form onsubmit={save}>
			<label for="note">Evidence note</label>
			<textarea id="note" bind:value={note}></textarea>
			<button type="submit" disabled={!selected || !note.trim() || busy}>Save note</button>
		</form>
		{#each notes as saved (saved.id)}
			<article>
				<p>{saved.note}</p>
				<small>{saved.record_id} / {saved.start} to {saved.end}</small>
			</article>
		{/each}
	</section>
</main>

<style>
	:global(*) {
		box-sizing: border-box;
	}
	:global(body) {
		margin: 0;
		background: #eeebe4;
		color: #223d2a;
		font-family: Arial, sans-serif;
	}
	main {
		max-width: 1000px;
		margin: auto;
		padding: 24px;
	}
	h1 {
		font-size: 2rem;
	}
	svg {
		width: 100%;
		max-width: 420px;
	}
	nav {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
	}
	button,
	textarea {
		font: inherit;
		max-width: 100%;
		padding: 10px;
		border: 1px solid #6e806e;
		border-radius: 5px;
	}
	button {
		background: #fff;
		color: #223d2a;
		cursor: pointer;
		overflow-wrap: anywhere;
		text-align: left;
	}
	button[aria-pressed=true] {
		background: #d5e5d2;
	}
	button:focus-visible,
	a:focus-visible,
	textarea:focus-visible {
		outline: 3px solid #a34718;
		outline-offset: 3px;
	}
	ul {
		list-style: none;
		padding: 0;
	}
	li,
	article {
		display: grid;
		gap: 9px;
		padding: 16px;
		background: #fff;
		margin-bottom: 10px;
		border-radius: 8px;
		overflow-wrap: anywhere;
	}
	a {
		color: #275331;
	}
	textarea {
		display: block;
		width: 100%;
		min-height: 90px;
		margin: 8px 0;
	}
	[role=alert] {
		padding: 12px;
		background: #f8d5ce;
	}
</style>