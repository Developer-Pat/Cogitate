// eslint-disable-next-line storybook/no-renderer-packages
import type { Meta, StoryObj } from '@storybook/react';
import { LoadingSkeleton, TableSkeleton, CardSkeleton, StatsSkeleton } from './LoadingSkeleton';

const meta = {
  title: 'Components/LoadingSkeleton',
  component: LoadingSkeleton,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof LoadingSkeleton>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {},
};

export const Table: StoryObj<{ rows: number }> = {
  render: (args) => <TableSkeleton {...args} />,
  args: {
    rows: 5,
  },
  argTypes: {
    rows: {
      control: { type: 'number', min: 1, max: 10 },
    },
  },
};

export const Card: StoryObj = {
  render: () => <CardSkeleton />,
  args: {},
};

export const Stats: StoryObj<{ count: number }> = {
  render: (args) => <StatsSkeleton {...args} />,
  args: {
    count: 4,
  },
  argTypes: {
    count: {
      control: { type: 'number', min: 1, max: 8 },
    },
  },
};