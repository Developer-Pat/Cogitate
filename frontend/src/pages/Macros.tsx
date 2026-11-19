/**
 * Macros Page
 * 
 * Dedicated page for macro management
 * Moved from ChatSettings to provide better UI space
 */

import { useState, useEffect } from 'react';
import { usePageTitle } from '../hooks/usePageTitle'
import { useNotificationStore } from '../stores/notificationStore'
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy, useSortable, arrayMove } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { MoreVertical } from 'lucide-react'
import { useSystemMacrosStore } from '../stores/macroSetsStore'
import { TopicFlyoutButton } from '../components/features/agentInteraction/TopicFlyoutButton'
import { AskExaButton } from '../components/agentPanel/AskExaButton';
import { HelpButton } from '../components/help';


// Sortable row component for drag-and-drop topic list
const SortableTopicRow = ({ id, label, isActive, isEmpty, onClick, onDelete }: {
  id: string
  label: string
  isActive: boolean
  isEmpty: boolean
  onClick: () => void
  onDelete: () => void
}) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id })
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }
  return (
    <div
      ref={setNodeRef}
      style={style}
      onClick={onClick}
      className={`flex items-center gap-2 px-3 py-2 rounded cursor-pointer transition-colors ${isActive ? 'bg-primary/20 text-primary' : 'hover:bg-base-300'} ${isDragging ? 'z-10 shadow-lg' : ''}`}
    >
      <div className="tooltip tooltip-bottom" data-tip="Drag to reorder">
        <span {...attributes} {...listeners} className="cursor-grab text-base-content/30 hover:text-base-content/60 text-sm select-none">
          ≡
        </span>
      </div>
      <span className="flex-1 text-sm truncate">{label}</span>
      {!isEmpty && (
        <span className="tooltip tooltip-bottom" data-tip="Delete macro">
          <span role="button" tabIndex={0} aria-label="Delete macro" className="text-xs text-readout cursor-pointer hover:text-error inline-block" onClick={(e) => { e.stopPropagation(); onDelete() }} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); onDelete(); } }}>
            ✕
          </span>
        </span>
      )}
    </div>
  )
}

export default function Macros() {
  usePageTitle('Macros', 'Manage your macro sets and meta topics')

  const [editingMacro, setEditingMacro] = useState<{ id: number; topic: string; description?: string; f1: string; f2: string; f3: string; f4: string; f5: string } | null>(null)
  const [isSaving, setIsSaving] = useState<boolean>(false)
  const [selectedTopicIndex, setSelectedTopicIndex] = useState<number>(0)
  const [showDeleteFlyout, setShowDeleteFlyout] = useState<number | null>(null)
  const [showAddPicker, setShowAddPicker] = useState<boolean>(false)
  const [confirmDeleteMetaTopic, setConfirmDeleteMetaTopic] = useState<number | null>(null)
  const selectedMetaTopicId = useSystemMacrosStore((s: any) => s.selectedMetaTopicId) // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
  const metaTopics = useSystemMacrosStore((s: any) => s.metaTopics) // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
  const macroSets = useSystemMacrosStore((s: any) => s.macroSets) // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
  // THE A-KEY SOURCE STATE (2026-09-03, the akeys Phase 3): the
  // meta-topic feeding the A1-A5 flyouts (the chat input's bank).
  // null = deactivated (no source configured).
  const aKeysMetaTopicId = useSystemMacrosStore((s: any) => s.aKeysMetaTopicId) // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
  const surface = useSystemMacrosStore((s: any) => s.surface) // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
  const selectedTopic = selectedMetaTopicId ? metaTopics.find((mt: any) => mt.id === selectedMetaTopicId) ?? null : null // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any

    // Load macro for editing when topic is selected
  useEffect(() => {
    const topic = metaTopics.find((mt: any) => mt.id === selectedMetaTopicId) // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
    if (!topic || !topic.topic_mappings || topic.topic_mappings.length === 0) {
      setEditingMacro(null)
      return
    }
    // THE EMPTY-SLOT FIX (2026-08-25, the user's report): an empty
    // M slot (no mapping at this index) must CLEAR the form — the
    // old fallback to topic_mappings[0] loaded the WRONG macro, and
    // the missing macroSet left the stale values in the inputs.
    const mapping = topic.topic_mappings[selectedTopicIndex]
    if (!mapping) {
      setEditingMacro(null)
      return
    }
    const macroSet = macroSets.find((m: any) => m.topic === mapping.topic) // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
    if (macroSet) {
      setEditingMacro({ id: macroSet.id, topic: macroSet.topic, description: (macroSet as any).description || '', f1: macroSet.f1_macro || '', f2: macroSet.f2_macro || '', f3: macroSet.f3_macro || '', f4: macroSet.f4_macro || '', f5: macroSet.f5_macro || '' }) // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
    } else {
      // an empty topic slot (no macro set yet) — the form clears
      setEditingMacro(null)
    }
  }, [selectedMetaTopicId, metaTopics, macroSets, selectedTopicIndex])

  // Load macro sets and meta-topics on mount
  useEffect(() => {
    useSystemMacrosStore.getState().loadAllMacros()
    useSystemMacrosStore.getState().loadMetaTopics()
  }, [])

  const [renamingMetaTopic, setRenamingMetaTopic] = useState<boolean>(false)
  const [renameValue, setRenameValue] = useState<string>('')
  const [renamingDescription, setRenamingDescription] = useState<boolean>(false)
  const [descriptionValue, setDescriptionValue] = useState<string>('')
  const [renamingMacroTopic, setRenamingMacroTopic] = useState<boolean>(false)
  const [macroTopicValue, setMacroTopicValue] = useState<string>('')

  const handleStartRename = () => {
    if (selectedTopic) {
      setRenameValue(selectedTopic.name)
      setRenamingMetaTopic(true)
    }
  }

  const handleSaveRename = async () => {
    if (!selectedMetaTopicId || !renameValue.trim()) return
    try {
      const response = await fetch('/api/v1/macros/meta-topics/' + selectedMetaTopicId, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: renameValue.trim() }),
      })
      if (!response.ok) throw new Error('HTTP ' + response.status)
      setRenamingMetaTopic(false)
      await useSystemMacrosStore.getState().loadMetaTopics()
      useNotificationStore.getState().addSuccess('Renamed', 'Meta-topic renamed')
    } catch (error) {
      useNotificationStore.getState().addError('Rename Failed', String(error))
    }
  }

  const handleStartDescriptionRename = () => {
    if (selectedTopic) {
      setDescriptionValue(selectedTopic.description || '')
      setRenamingDescription(true)
    }
  }

  const handleSaveDescription = async () => {
    if (!selectedMetaTopicId) return
    try {
      const response = await fetch('/api/v1/macros/meta-topics/' + selectedMetaTopicId, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: descriptionValue }),
      })
      if (!response.ok) throw new Error('HTTP ' + response.status)
      setRenamingDescription(false)
      await useSystemMacrosStore.getState().loadMetaTopics()
      useNotificationStore.getState().addSuccess('Saved', 'Description updated')
    } catch (error) {
      useNotificationStore.getState().addError('Save Failed', String(error))
    }
  }

  const handleStartMacroTopicRename = () => {
    if (editingMacro) {
      setMacroTopicValue(editingMacro.topic)
      setRenamingMacroTopic(true)
    }
  }

  const handleSaveMacroTopic = async () => {
    if (!editingMacro || !macroTopicValue.trim()) return
    try {
      const response = await fetch('/api/v1/macros/' + editingMacro.id, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: macroTopicValue.trim() }),
      })
      if (!response.ok) throw new Error('HTTP ' + response.status)
      setRenamingMacroTopic(false)
      setEditingMacro({ ...editingMacro, topic: macroTopicValue.trim() })
      // BOTH lists. The rename also repoints every meta-topic mapping that named the OLD
      // topic — the backend does that in the same request — so refetching only the macro
      // sets would leave the slot rendering the stale name until a page reload.
      await useSystemMacrosStore.getState().loadAllMacros()
      await useSystemMacrosStore.getState().loadMetaTopics()
      useNotificationStore.getState().addSuccess('Saved', 'Macro set topic renamed')
    } catch (error) {
      useNotificationStore.getState().addError('Save Failed', String(error))
    }
  }

  const [availableSaves, setAvailableSaves] = useState<any[]>([]) // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
  const [showLoadPicker, setShowLoadPicker] = useState(false)
  const [savingMeta, setSavingMeta] = useState(false)
  const [loadingMeta, setLoadingMeta] = useState(false)

  const handleSaveMetaTopic = async () => {
    if (!selectedMetaTopicId) return
    setSavingMeta(true)
    try {
      const r = await fetch('/api/v1/macros/meta-topics/' + selectedMetaTopicId + '/save', { method: 'POST' })
      if (!r.ok) throw new Error('HTTP ' + r.status)
      const d = await r.json()
      useNotificationStore.getState().addSuccess('Saved', d.message || 'Meta-topic saved to file')
    } catch (err) {
      useNotificationStore.getState().addError('Save Failed', String(err))
    }
    setSavingMeta(false)
  }

  const handleLoadSaves = async () => {
    try {
      const r = await fetch('/api/v1/macros/saves')
      if (!r.ok) throw new Error('HTTP ' + r.status)
      const d = await r.json()
      setAvailableSaves(d.saves || [])
      setShowLoadPicker(true)
    } catch (err) {
      useNotificationStore.getState().addError('Load Failed', String(err))
    }
  }

  const handleLoadMetaTopic = async (folder: string) => {
    setLoadingMeta(true)
    setShowLoadPicker(false)
    try {
      const r = await fetch('/api/v1/macros/meta-topics/load/' + folder, { method: 'POST' })
      if (!r.ok) throw new Error('HTTP ' + r.status)
      const data = await r.json()
      // Refresh store
      await useSystemMacrosStore.getState().loadMetaTopics()
      useSystemMacrosStore.getState().selectMetaTopic(data.meta_topic_id)
      await useSystemMacrosStore.getState().loadAllMacros()
      // Directly populate the editor from loaded data
      const metaTopics = useSystemMacrosStore.getState().metaTopics
      const macros = useSystemMacrosStore.getState().macros
      const topic = metaTopics.find((mt: any) => mt.id === data.meta_topic_id) // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
      if (topic?.topic_mappings?.length) {
        const mapping = topic.topic_mappings[0]
        const macroSet = macros.find((m: any) => m.topic === mapping.topic) // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
        if (macroSet) {
          setEditingMacro({
            id: Number(macroSet.id), topic: macroSet.topic,
            description: (macroSet as any).description || '', // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
            f1: macroSet.f1_macro || '', f2: macroSet.f2_macro || '',
            f3: macroSet.f3_macro || '', f4: macroSet.f4_macro || '',
            f5: macroSet.f5_macro || '',
          })
        }
      }
      setSelectedTopicIndex(0)
      useNotificationStore.getState().addSuccess('Loaded', 'Meta-topic loaded from file')
    } catch (err) {
      useNotificationStore.getState().addError('Load Failed', String(err))
    }
    setLoadingMeta(false)
  }

  const handleClearSelection = () => {
    useSystemMacrosStore.getState().selectMetaTopic(null)
    setEditingMacro(null)
    setSelectedTopicIndex(0)
  }

  // THE FORM-ONLY CLEAR (2026-08-25, the user's report): the
  // editing-form Clear must clear the FORM (the F-key inputs)
  // WITHOUT deselecting the meta-topic — the old handler nuked the
  // whole selection. The EMPTY F-keys (not a null) keep the form
  // visible + ready to type (a null collapses the pane).
  const handleClearForm = () => {
    setEditingMacro(prev => prev ? { ...prev, f1: '', f2: '', f3: '', f4: '', f5: '' } : prev)
  }

  const handleDeleteMetaTopic = async () => {
    if (!selectedMetaTopicId) return
    try {
      const response = await fetch('/api/v1/macros/meta-topics/' + selectedMetaTopicId, { method: 'DELETE' })
      if (!response.ok) throw new Error('HTTP ' + response.status)
      setConfirmDeleteMetaTopic(null)
      setEditingMacro(null)
      setSelectedTopicIndex(0)
      await useSystemMacrosStore.getState().loadMetaTopics()
      useNotificationStore.getState().addSuccess('Deleted', 'Meta-topic deleted')
    } catch (error) {
      useNotificationStore.getState().addError('Delete Failed', String(error))
    }
  }

  const handleCreateNewMetaTopic = async () => {
    try {
      const response = await fetch('/api/v1/macros/meta-topics', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'New Meta-Topic', description: '', topic_mappings: [], namespace: 'agent', is_active: true }),
      })
      if (!response.ok) throw new Error('HTTP ' + response.status)
      const created = await response.json()
      await useSystemMacrosStore.getState().loadMetaTopics()
      setEditingMacro(null)
      useSystemMacrosStore.getState().selectMetaTopic(created.id)
      useNotificationStore.getState().addSuccess('Created', 'New meta-topic created')
    } catch (error) {
      useNotificationStore.getState().addError('Create Failed', String(error))
    }
  }


  const handleReorderTopicMappings = async (newMappings: any[]) => { // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
    if (!selectedTopic || !selectedMetaTopicId) return
    try {
      const response = await fetch(`/api/v1/macros/meta-topics/${selectedMetaTopicId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic_mappings: newMappings }),
      })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      await useSystemMacrosStore.getState().loadMetaTopics()
      useNotificationStore.getState().addSuccess('Reordered', 'Topic order updated')
    } catch (error) {
      useNotificationStore.getState().addError('Reorder Failed', String(error))
    }
  }

  const handleDragEnd = (event: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
    const { active, over } = event
    if (!over || active.id === over.id) return
    const mappings = selectedTopic?.topic_mappings ?? []
    const oldIndex = mappings.findIndex((m: any) => m.topic === active.id) // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
    const newIndex = mappings.findIndex((m: any) => m.topic === over.id) // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
    if (oldIndex === -1 || newIndex === -1) return
    const newMappings = arrayMove(mappings, oldIndex, newIndex)
    setEditingMacro(null)
    handleReorderTopicMappings(newMappings)
  }
    const handleRemoveTopic = async (index: number) => {
    if (!selectedTopic || !selectedMetaTopicId) return
    const newMappings = selectedTopic.topic_mappings.filter((_: any, i: number) => i !== index) // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
    try {
      const response = await fetch(`/api/v1/macros/meta-topics/${selectedMetaTopicId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic_mappings: newMappings }),
      })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      await useSystemMacrosStore.getState().loadMetaTopics()
      setEditingMacro(null)
      setSelectedTopicIndex(0)
      useNotificationStore.getState().addSuccess('Removed', 'Topic removed from meta-topic')
    } catch (error) {
      useNotificationStore.getState().addError('Remove Failed', String(error))
    }
  }

  const handleDeleteMacroSet = async (mapping: any) => { // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
    if (!mapping) return
    const macroSet = macroSets.find((m: any) => m.topic === mapping.topic) // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
    if (!macroSet) return
    try {
      const response = await fetch(`/api/v1/macros/${macroSet.id}`, { method: 'DELETE' })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      await useSystemMacrosStore.getState().loadAllMacros()
      await handleRemoveTopic(selectedTopicIndex)
      useNotificationStore.getState().addSuccess('Deleted', 'Macro set deleted')
    } catch (error) {
      useNotificationStore.getState().addError('Delete Failed', String(error))
    }
  }

  const handleAddTopic = async (macroSetId: number) => {
    if (!selectedTopic || !selectedMetaTopicId) return
    const macroSet = macroSets.find((m: any) => m.id === macroSetId) // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
    if (!macroSet) return
    const newMapping = { topic: macroSet.topic, slot_start: 'F1' }
    const newMappings = [...(selectedTopic.topic_mappings || []), newMapping].slice(0, 5)
    try {
      const response = await fetch(`/api/v1/macros/meta-topics/${selectedMetaTopicId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic_mappings: newMappings }),
      })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      await useSystemMacrosStore.getState().loadMetaTopics()
      setShowAddPicker(false)
      useNotificationStore.getState().addSuccess('Added', 'Topic added to meta-topic')
    } catch (error) {
      useNotificationStore.getState().addError('Add Failed', String(error))
    }
  }

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }))

  const handleSaveMacro = async () => {
    if (!editingMacro) return
    setIsSaving(true)
    try {
      const response = await fetch(`/api/v1/macros/${editingMacro.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          topic: editingMacro.topic,
          description: editingMacro.description,
          f1_macro: editingMacro.f1, f2_macro: editingMacro.f2, 
          f3_macro: editingMacro.f3, f4_macro: editingMacro.f4, 
          f5_macro: editingMacro.f5 
        }),
      })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      useNotificationStore.getState().addSuccess('Saved', 'Macro set updated successfully')
      useSystemMacrosStore.getState().loadAllMacros()
    } catch (err) {
      useNotificationStore.getState().addError('Save Failed', String(err))
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="min-h-screen bg-base-100 p-6">
      <div className="max-w-[1400px] mx-auto w-full">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold mb-2">Macro Management</h1>
            <p className="text-readout">
              Select a meta-topic, then click a topic slot to edit its F1-F5 macros. Drag to reorder, or use the buttons below to add/remove topics.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <AskExaButton context="macros" tooltip="Ask Exa to generate or maintain macros" label="Ask Exa" />
            <HelpButton context="macros" tooltipPosition="bottom" />
          </div>
        </div>

        {/* Load Picker Flyout */}
        {showLoadPicker && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={() => setShowLoadPicker(false)}>
            <div className="card bg-base-200 shadow-xl w-96 max-h-96 overflow-y-auto" onClick={e => e.stopPropagation()}>
              <div className="card-body p-4">
                <h3 className="font-semibold text-sm mb-3">Load Meta-Topic from File</h3>
                {availableSaves.length === 0 && <p className="text-xs text-readout">No saved meta-topics found in macros/ folder.</p>}
                {availableSaves.map((s: any) => ( // eslint-disable-line @typescript-eslint/no-explicit-any -- legacy-any
                  <button
                    key={s.folder}
                    className="flex items-center gap-3 px-3 py-2 rounded hover:bg-base-300 text-left w-full transition-colors"
                    onClick={() => handleLoadMetaTopic(s.folder)}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{s.name}</p>
                      <p className="text-xs text-readout truncate">{s.macro_set_count} macro sets — {s.description}</p>
                    </div>
                  </button>
                ))}
              </div>
                     <div className="flex items-center gap-2">
            <HelpButton context="macros" tooltipPosition="bottom" />
          </div>
        </div>
          </div>
        )}

        {/* Two-Panel Layout: Topic List + F-Key Editor */}
        <div className="grid grid-cols-1 md:grid-cols-[280px_1fr] gap-4 mb-6">
          {/* Left Panel: Topic List */}
          <div className="card bg-base-200 shadow-sm">
            <div className="card-body p-3">
              <div className="flex items-center gap-1 mb-3 flex-wrap">
                <TopicFlyoutButton size="sm" label="Select Meta" />
                {/* The three-dot action menu (the usual UI hack) */}
                <div className="dropdown dropdown-end">
                  <div className="tooltip tooltip-top" data-tip="More actions">
                    <button
                      tabIndex={0}
                      type="button"
                      className="btn btn-ghost btn-xs btn-square"
                      aria-label="More actions"
                    >
                      <MoreVertical className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <ul tabIndex={0} className="dropdown-content z-[1] menu p-2 shadow bg-base-100 rounded-box w-48 text-xs">
                    <li><button onClick={handleCreateNewMetaTopic}>Create meta-topic</button></li>
                    <li>
                      <button
                        onClick={() => selectedMetaTopicId && setConfirmDeleteMetaTopic(selectedMetaTopicId)}
                        disabled={!selectedMetaTopicId}
                        className="text-error"
                      >
                        Delete meta-topic
                      </button>
                    </li>
                    <li>
                      <button onClick={handleClearSelection} disabled={!selectedMetaTopicId}>
                        Clear selection
                      </button>
                    </li>
                    <li>
                      <button onClick={handleSaveMetaTopic} disabled={!selectedMetaTopicId || savingMeta}>
                        Save to file
                      </button>
                    </li>
                    <li>
                      <button onClick={handleLoadSaves} disabled={loadingMeta}>
                        Load from file
                      </button>
                    </li>
                  </ul>
                </div>
              </div>
              {selectedMetaTopicId && selectedTopic && !renamingMetaTopic && (
                <div className="tooltip tooltip-top" data-tip="Click to rename">
                  <p className="text-xs text-readout mb-2 cursor-pointer hover:text-primary" onClick={handleStartRename}>
                    Meta-topic: <span className="font-semibold">{selectedTopic.name}</span>
                  </p>
                </div>
              )}

              {/* THE A-KEY SOURCE — THE AUDIT READOUT (2026-09-03, the
                  akeys Phase 5d): the SELECTION lives on the chat
                  keyboards now — the bank-attached selectors (the F
                  icon after M5, the A icon beside the A keys) set +
                  persist directly. This page only SHOWS the current
                  A source (of the active surface). */}
              <div className="border-t border-base-300 pt-2 mt-2 mb-3">
                <div className="text-[10px] uppercase tracking-wide text-readout mb-1 flex items-center gap-1">
                  <span>A-Key source (surface: {surface})</span>
                </div>
                <p className="text-xs text-readout">
                  {aKeysMetaTopicId !== null ? (
                    <span className="badge badge-xs badge-primary badge-outline normal-case">
                      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any -- legacy-any */}
                      {metaTopics.find((mt: any) => mt.id === aKeysMetaTopicId)?.name ?? 'unresolved'}
                    </span>
                  ) : (
                    <span className="badge badge-xs badge-ghost normal-case">none — A-keys deactivated</span>
                  )}
                  <span className="ml-1.5 text-readout">
                    — change it on the chat input's A selector (select = the new source)
                  </span>
                </p>
              </div>
              {renamingMetaTopic && (
                <div className="flex items-center gap-1 mb-2">
                  <input
                    className="input input-bordered input-xs w-full"
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleSaveRename(); if (e.key === 'Escape') setRenamingMetaTopic(false) }}
                    onBlur={(e) => {
                      // Only close if focus didn't move to the Save button
                      if (!e.currentTarget.parentElement?.contains(e.relatedTarget as Node)) {
                        setRenamingMetaTopic(false)
                      }
                    }}
                    autoFocus
                  />
                  <button className="btn btn-primary btn-xs" onClick={handleSaveRename}>Save</button>
                </div>
              )}
              {/* Meta-topic description */}
              {selectedMetaTopicId && selectedTopic && !renamingDescription && (
                <div className="tooltip tooltip-top" data-tip="Click to edit description">
                  <p className="text-xs text-readout mb-2 cursor-pointer hover:text-primary" onClick={handleStartDescriptionRename}>
                    {selectedTopic.description || <span className="italic">Add description...</span>}
                  </p>
                </div>
              )}
              {renamingDescription && (
                <div className="flex items-center gap-1 mb-2">
                  <textarea
                    className="textarea textarea-bordered textarea-xs w-full"
                    value={descriptionValue}
                    onChange={(e) => setDescriptionValue(e.target.value)}
                    onBlur={(e) => {
                      if (!e.currentTarget.parentElement?.contains(e.relatedTarget as Node)) {
                        setRenamingDescription(false)
                      }
                    }}
                    autoFocus
                    rows={2}
                  />
                  <button className="btn btn-primary btn-xs" onClick={handleSaveDescription}>Save</button>
                </div>
              )}
              <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragEnd={handleDragEnd}
              >
                {/* eslint-disable @typescript-eslint/no-explicit-any -- legacy-any: the type-debt backlog (the tsc -b sweep 2026-08-26) */}
                <SortableContext items={selectedTopic?.topic_mappings?.map((m: any) => m.topic) ?? []} strategy={verticalListSortingStrategy}>
                  <div className="space-y-1">
                    {[0,1,2,3,4].map(i => {
                      const mapping = selectedTopic?.topic_mappings?.[i] ?? null
                      const macroSet = mapping ? macroSets.find((m: any) => m.topic === mapping.topic) : null  
                      const isActive = selectedTopicIndex === i && macroSet
                      const sortableId = mapping?.topic ?? `empty-${i}`
                      return (
                        <SortableTopicRow
                          key={sortableId}
                          id={sortableId}
                          label={mapping ? mapping.topic : `Slot M${i+1}`}
                          isActive={isActive}
                          isEmpty={!macroSet}
                          onClick={() => {
                            setSelectedTopicIndex(i)
                            if (macroSet) {
                              setEditingMacro({ id: macroSet.id, topic: macroSet.topic, description: (macroSet as any).description || '', f1: macroSet.f1_macro || '', f2: macroSet.f2_macro || '', f3: macroSet.f3_macro || '', f4: macroSet.f4_macro || '', f5: macroSet.f5_macro || '' })  
                            }
                          }}
                          onDelete={() => setShowDeleteFlyout(i)}
                        />
                      )
                    })}
                  </div>
                </SortableContext>
              </DndContext>
              {showDeleteFlyout !== null && (
                <div className="fixed inset-0 z-50" onClick={() => setShowDeleteFlyout(null)}>
                  <div className="absolute bg-base-100 border border-base-300 rounded-lg shadow-xl p-2 z-50" style={{ top: '50%', left: '50%', transform: 'translate(-50%, -50%)', minWidth: '200px' }} onClick={(e) => e.stopPropagation()}>
                    <button className="w-full text-left px-3 py-2 text-sm hover:bg-base-200 rounded" onClick={() => { const idx = showDeleteFlyout; setShowDeleteFlyout(null); handleRemoveTopic(idx) }}>
                      Remove from Topic
                    </button>
                    <button className="w-full text-left px-3 py-2 text-sm hover:bg-base-200 rounded text-error" onClick={() => { const mapping = selectedTopic?.topic_mappings?.[showDeleteFlyout]; setShowDeleteFlyout(null); if (mapping) handleDeleteMacroSet(mapping) }}>
                      Delete Macro Set
                    </button>
                  </div>
                </div>
              )}
              {confirmDeleteMetaTopic !== null && (
                <div className="fixed inset-0 z-50" onClick={() => setConfirmDeleteMetaTopic(null)}>
                  <div className="absolute bg-base-100 border border-base-300 rounded-lg shadow-xl p-4 z-50" style={{ top: '50%', left: '50%', transform: 'translate(-50%, -50%)', maxWidth: '350px' }} onClick={(e) => e.stopPropagation()}>
                    <h4 className="font-semibold text-sm mb-2">Delete Meta-Topic?</h4>
                    <p className="text-xs text-readout mb-4">This will permanently delete the meta-topic and its topic mappings. This action cannot be undone.</p>
                    <div className="flex justify-end gap-2">
                      <button className="btn btn-neutral btn-ghost btn-xs" onClick={() => setConfirmDeleteMetaTopic(null)}>Cancel</button>
                      <button className="btn btn-error btn-xs" onClick={handleDeleteMetaTopic}>Delete</button>
                    </div>
                  </div>
                </div>
              )}
              {showAddPicker && (
                <div className="fixed inset-0 z-50" onClick={() => setShowAddPicker(false)}>
                  <div className="absolute bg-base-100 border border-base-300 rounded-lg shadow-xl p-3 z-50" style={{ top: '50%', left: '50%', transform: 'translate(-50%, -50%)', minWidth: '300px', maxHeight: '400px', overflowY: 'auto' }} onClick={(e) => e.stopPropagation()}>
                    <h4 className="text-sm font-semibold mb-2">Select Macro Set to Add</h4>
                    {macroSets
                      .filter((m: any) => !selectedTopic?.topic_mappings?.some((tm: any) => tm.topic === m.topic))  
                      .slice(0, 20)
                      .map((m: any) => (  
                        <button key={m.id} className="w-full text-left px-3 py-2 text-sm hover:bg-base-200 rounded truncate" onClick={() => handleAddTopic(m.id)}>
                          {m.topic || m.name}
                        </button>
                      ))}
                    {macroSets.filter((m: any) => !selectedTopic?.topic_mappings?.some((tm: any) => tm.topic === m.topic)).length === 0 && (  
                      <p className="text-xs text-readout">No more macro sets available</p>
                    )}
                  </div>
                </div>
              )}
              <button className="btn btn-outline btn-xs mt-2 w-full" disabled={!selectedTopic} onClick={() => setShowAddPicker(true)}>
                + Add Topic
              </button>
            </div>
          </div>

          {/* Right Panel: F-Key Editor */}
          <div className="card bg-base-200 shadow-sm">
            <div className="card-body p-3">
              <div className="flex items-center justify-between mb-3">
                {editingMacro && renamingMacroTopic ? (
                  <div className="flex items-center gap-1 flex-1">
                    <input
                      className="input input-bordered input-xs w-full"
                      value={macroTopicValue}
                      onChange={(e) => setMacroTopicValue(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') handleSaveMacroTopic(); if (e.key === 'Escape') setRenamingMacroTopic(false) }}
                      onBlur={(e) => {
                        if (!e.currentTarget.parentElement?.contains(e.relatedTarget as Node)) {
                          setRenamingMacroTopic(false)
                        }
                      }}
                      autoFocus
                    />
                    <button className="btn btn-primary btn-xs" onClick={handleSaveMacroTopic}>Save</button>
                  </div>
                ) : (
                  <h2 className="card-title text-lg cursor-pointer hover:text-primary" onClick={editingMacro ? handleStartMacroTopicRename : undefined}>
                    {editingMacro ? `Topic: ${editingMacro.topic}` : 'F-Key Macros'}
                  </h2>
                )}
              </div>
              {/* Macro Set Description */}
              {editingMacro && (
                <div className="mb-2">
                  <p className="text-xs text-readout mb-1">Description:</p>
                  <input
                    className="input input-bordered input-xs w-full"
                    value={(editingMacro as any).description || ''}  
                    onChange={(e) => editingMacro && setEditingMacro({ ...editingMacro, description: e.target.value })}
                    placeholder="Macro set description..."
                  />
                </div>
              )}
              <div className="space-y-1">
                {['f1','f2','f3','f4','f5'].map((key, i) => (
                  <div key={key} className="flex items-center gap-2">
                    <span className="font-semibold text-sm w-8 flex-shrink-0 text-right">F{i + 1}:</span>
                    <input
                      className="input input-bordered w-full font-mono text-sm h-8 min-h-0 py-0"
                      value={(editingMacro as any)?.[key] || ''}  
                      onChange={(e) => editingMacro && setEditingMacro({ ...editingMacro, [key]: e.target.value })}
                      placeholder="Macro text..."
                    />
                  </div>
                ))}
              </div>
              {editingMacro && (
                <div className="flex justify-end items-center gap-2 mt-3">
                  {/* THE RIGHT-PANE CLEAR (2026-08-25, the user's ask):
                      left of the Save — clears the editing form + the
                      selection. */}
                  <div className="tooltip tooltip-top" data-tip="Clear the editing form">
                    <button
                      onClick={handleClearForm}
                      className="btn btn-ghost btn-sm"
                      disabled={!editingMacro}
                    >
                      Clear
                    </button>
                  </div>
                  <button onClick={handleSaveMacro} disabled={isSaving || !editingMacro} className="btn btn-primary btn-sm">
                    {isSaving ? 'Saving...' : 'Save'}
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>        {/* Bottom Section - Tools (Full Width) */}
        <div className="space-y-6 mb-6">
  




        </div>
        </div>
      </div>
  )
}
