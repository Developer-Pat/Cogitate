// eslint-disable-next-line storybook/no-renderer-packages
import type { Meta, StoryObj } from '@storybook/react';
import { NotificationContainer } from './NotificationContainer';

const meta: Meta<typeof NotificationContainer> = {
  title: 'Components/NotificationContainer',
  component: NotificationContainer,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {},
};